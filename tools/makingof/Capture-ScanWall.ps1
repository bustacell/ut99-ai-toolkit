<#
.SYNOPSIS
  Footage for the scan wall: play every demo of the run at 32x exactly like a scan (blank HUD, no gore, rich
  logging on) with the game visible, and record each one with OBS. Writes nothing into any scan folder.
  Back up the UT and OBS settings before (Setup.ps1 style) and restore them afterwards; see docs/MAKINGOF.md.
.EXAMPLE
  .\Capture-ScanWall.ps1 X:\UTDD-run\demos X:\UTDD\output\work\makingof\scanwall
#>
param(
    [Parameter(Mandatory, Position = 0)][string]$DemoDir,
    [Parameter(Mandatory, Position = 1)][string]$OutDir,
    [double]$Speed = 32
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
$tools = Split-Path -Parent $PSScriptRoot          # the toolkit's tools folder
Import-Module (Join-Path $tools 'UTDirector.psm1') -Force
Import-Module (Join-Path $tools 'OBSWebSocket.psm1') -Force
New-Item -ItemType Directory -Force $OutDir | Out-Null
$index = New-Object System.Collections.Generic.List[object]
$indexFile = Join-Path $OutDir 'index.json'
if (Test-Path -LiteralPath $indexFile) { foreach ($x in @(Get-Content -LiteralPath $indexFile -Raw | ConvertFrom-Json)) { $index.Add($x) } }   # resume

Start-OBSApp
for ($i = 0; $i -lt 30; $i++) { try { Connect-OBS -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1; Confirm-OBSCrashDialog } }
Set-UTKeepAwake $true

try {
    foreach ($demo in Get-ChildItem -LiteralPath $DemoDir -Filter *.dem | Sort-Object Name) {
        $name = $demo.BaseName
        $target = Join-Path $OutDir "$name.mkv"
        if (Test-Path -LiteralPath $target) { continue }
        [void](Start-UTDemo $demo.FullName)
        Send-UTCommand 'ddhud 0', 'ddnogore 1', 'ddrich 1', 'ddstatus' -SettleMs 400
        # Brightness check while the demo runs at 1x for a moment: the very first frame of a map can be black
        # (level fade-in, spawn in a dark corner), which is not a capture failure.
        $luma = 0.0
        foreach ($try in 1..2) {
            foreach ($k in 1..8) { $l = Get-OBSSourceLuma; if ($l -gt $luma) { $luma = $l }; if ($luma -ge 6) { break }; Start-Sleep -Milliseconds 500 }
            if ($luma -ge 6) { break }
            if ($try -eq 1) { Restart-OBSApp; Start-Sleep 2 }
        }
        if ($luma -lt 6) { throw "OBS capture is black for $name (luma $([math]::Round($luma, 1)))" }
        Send-UTCommand 'pause', 'seekto 0', 'ddstatus' -SettleMs 600
        [void](Invoke-OBS StartRecord)
        Start-Sleep -Milliseconds 800
        $wall0 = Get-Date
        Send-UTCommand 'pause', ("slomo {0}" -f $Speed.ToString($inv)), 'ddstatus' -SettleMs 300
        $total = 0.0; $t = 0.0; $lastT = -1.0
        $stall = [Diagnostics.Stopwatch]::StartNew(); $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($true) {
            Start-Sleep -Milliseconds 400
            $last = Read-UTLogNew | Where-Object { $_ -match 'DD\|(STATE|STATUS)\|' } | Select-Object -Last 1
            if ($last) {
                $s = ConvertFrom-DDLine $last
                $tt = 0.0; [void][double]::TryParse([string]$s.total, [Globalization.NumberStyles]::Float, $inv, [ref]$tt)
                if ($tt -gt 0) { $total = $tt; $t = [double]$s.t; if ($t -ne $lastT) { $lastT = $t; $stall.Restart() } }
            }
            if ($total -gt 0 -and $t -ge $total - 0.6) { break }
            if ($stall.Elapsed.TotalSeconds -gt 10) { Write-Warning "stalled at t=$t in $name"; break }
            if ($sw.Elapsed.TotalMinutes -gt 10) { Write-Warning "timeout in $name"; break }
        }
        $wall1 = Get-Date
        $stop = Invoke-OBS StopRecord
        Stop-UT
        Start-Sleep 2
        Move-Item -LiteralPath $stop.outputPath -Destination $target -Force
        $index.Add([ordered]@{ demo = $name; file = $target; demoSeconds = [math]::Round($total, 2); reachedSeconds = [math]::Round($t, 2)
                               speed = $Speed; wallStart = $wall0.ToString('s'); wallSeconds = [math]::Round(($wall1 - $wall0).TotalSeconds, 1); luma = [math]::Round($luma, 1) })
        $index.ToArray() | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $OutDir 'index.json') -Encoding UTF8
    }
} finally {
    Set-UTKeepAwake $false
    if (Get-UTProcess) { try { Stop-UT } catch {} }
}
"scan wall: $($index.Count) demos recorded -> $OutDir"
