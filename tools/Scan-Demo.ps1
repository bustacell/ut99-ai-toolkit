<#
.SYNOPSIS
  Play a demo fast (no HUD) and extract a timestamped event list: kills, multi-kills,
  sprees, flag events. Writes <output>\scans\<demo>.events.json and returns a summary.
.EXAMPLE
  .\Scan-Demo.ps1 -Demo CTF-2on2-Crates2022_03-07_00-43-36.dem -Speed 32
#>
param(
    [Parameter(Mandatory)][string]$Demo,
    [double]$Speed = 32,
    [switch]$KeepGameOpen
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force

. (Join-Path $PSScriptRoot 'DDConfig.ps1')
$demoPath = Resolve-DDDemo $Demo   # throws "EXTERNAL DRIVE NOT CONNECTED: ..." when a demo folder is unreachable
$name = Get-DDDemoId $demoPath    # file name, or "<name>~<size>" when another recording has the same name
$outDir = Join-Path $DDOut 'scans'
New-Item -ItemType Directory -Force $outDir | Out-Null

[void](Start-UTDemo $demoPath)
# Heavy demos (NPLoader/ACE servers) freeze UT for ~10 s right after the watcher appears; keys posted meanwhile are
# lost. Wait until the window responds again before sending the scan commands (the speed guard resends them anyway).
$ws = [Diagnostics.Stopwatch]::StartNew()
while ($ws.Elapsed.TotalSeconds -lt 60) {
    $u = Get-UTProcess
    if (-not $u) { throw 'UT exited after the demo started' }
    if ($u.Responding) { break }
    Start-Sleep -Milliseconds 500
}
$lines = New-Object System.Collections.Generic.List[string]
# ddnogore: gibs/carcasses/blood are only render load at 32x; no data comes from them
Send-UTCommand 'ddhud 0', 'ddnogore 1', 'ddrich 1', ("slomo {0}" -f $Speed.ToString($inv)), 'ddstatus' -SettleMs 300
$sw = [Diagnostics.Stopwatch]::StartNew()
$total = $null; $lastT = -1; $stall = [Diagnostics.Stopwatch]::StartNew()
# Speed guard: the keypress that delivers 'playback 0' / 'slomo' is sometimes lost (then the demo crawls at ~0.6x).
# Resend whenever the reported speed is low or demo time advances far slower than requested.
$fix = [Diagnostics.Stopwatch]::StartNew(); $fixes = 0; $rateT0 = $null; $kicks = 0
while ($true) {
    Start-Sleep -Milliseconds 500
    foreach ($l in (Read-UTLogNew)) {
        if ($l -match '^Critical:') { throw "UT crashed: $l" }
        if ($l -like 'DemoDirector: DD|*') { $lines.Add($l) }
    }
    $last = $lines.ToArray() | Where-Object { $_ -match 'DD\|(STATE|STATUS)\|' } | Select-Object -Last 1
    if ($last) {
        $s = ConvertFrom-DDLine $last
        $tt = 0.0; [void][double]::TryParse([string]$s.total, [Globalization.NumberStyles]::Float, $inv, [ref]$tt)
    }
    if ($last -and $tt -gt 0) {   # a STATE line without a valid total (no demo driver yet) is skipped, the stall check still runs
        $total = $tt
        $t = [double]$s.t
        if ($s.t -ne $lastT) { $lastT = $s.t; $stall.Restart() }
        if ($t -ge $total - 0.6) { break }
        if ($null -eq $rateT0) { $rateT0 = $t; $fix.Restart() }
        $sp = 0.0; $slowSpeed = [double]::TryParse([string]$s.speed, [Globalization.NumberStyles]::Float, $inv, [ref]$sp) -and $sp -lt $Speed * 0.9
        $slowRate = $fix.Elapsed.TotalSeconds -ge 4 -and (($t - $rateT0) / $fix.Elapsed.TotalSeconds) -lt [math]::Min(4, $Speed / 4)
        if (($slowSpeed -and $fix.Elapsed.TotalSeconds -ge 2) -or $slowRate) {
            if ($fixes -lt 10) {
                # (no Escape here any more: DDConsole runs Scroll Lock even while a UWindow popup is open, and Escape
                #  would open the UT menu)
                Send-UTCommand 'playback 0', ("slomo {0}" -f $Speed.ToString($inv)), 'ddstatus' -SettleMs 300
                $fixes++
            }
            $rateT0 = $t; $fix.Restart()
        } elseif ($fix.Elapsed.TotalSeconds -ge 8) { $rateT0 = $t; $fix.Restart() }   # rolling window
    }
    # Demos from servers with NPLoader/ACE sometimes freeze UT for good right after "[NPLoader] Loading complete"
    # (window not responding, no status line). No command helps; Scan-All kills UT and starts the demo again.
    # 30 s, not less: the normal post-load freeze lasts ~10 s (6 s made every such demo fail all 5 retries).
    if (-not $total -and $stall.Elapsed.TotalSeconds -gt 30) { Write-Warning 'No status line (UT hung at startup)'; break }
    if ($stall.Elapsed.TotalSeconds -gt 8) { Write-Warning "Playback stalled at t=$lastT"; break }
    if ($sw.Elapsed.TotalMinutes -gt 30) { throw 'Scan timeout' }
}
# players at the end of the demo (final scores)
Send-UTCommand 'ddplayers' -SettleMs 800
foreach ($l in (Read-UTLogNew)) { if ($l -like 'DemoDirector: DD|*') { $lines.Add($l) } }
# slomo is saved to UnrealTournament.ini ([Engine.GameInfo] GameSpeed): left at the scan speed, every game started
# afterwards (playtests, the user's own games) runs 16-32x fast
Send-UTCommand 'slomo 1' -SettleMs 300
if (-not $KeepGameOpen) { Stop-UT }
if (-not $total) { throw 'No demo data (never got a valid demo length)' }   # FAIL, so a rerun retries it

# --- parse -----------------------------------------------------------------------
# Kill wordings beyond the three generic ones above; keep in sync with tools\kill_messages.py.
# [pattern, fixed weapon or $null]. "You were killed by X!" is the local copy of a public line: never a kill.
$killPatterns = @(
    @('^(?<k>.+?) (?:electrified|gibbed|sliced) (?<v>.+?) with (?:the |a |an )?(?<w>.+?)\.$', $null),
    @('^(?<k>.+?) riddled (?<v>.+?) full of holes with (?:the |a |an )?(?<w>.+?)\.$', $null),
    @('^(?<k>.+?) ripped a chunk of meat out of (?<v>.+?) with (?:the |a |an )?(?<w>.+?)\.$', $null),
    @("^(?<k>.+?) put a bullet through (?<v>.+?)'s head\.$", 'Sniper Rifle (headshot)'),
    @("^(?<k>.+?)'s (?<w>.+?) turned (?<v>.+?) into a leaky piece of meat\.$", $null),
    @("^(?<v>.+?) was smacked down(?: multiple times)? by (?<k>.+?)'s (?<w>.+?)\.$", $null),
    @("^(?<v>.+?) was ripped to shreds by (?<k>.+?)'s (?<w>.+?)\.$", $null),
    @("^(?<v>.+?) was vaporized by (?<k>.+?)'s (?<w>.+?)!+$", $null),
    @("^(?<v>.+?) was killed by (?<k>.+?)'s (?<w>.+?)\.$", $null),
    @("^(?<v>.+?) got smeared by (?<k>.+?)'s piston\.$", 'Impact Hammer'),
    @("^(?<v>.+?) ate (?<k>.+?)'s burning plasma death\.$", 'Pulse Gun'),
    @("^(?<v>.+?) drank a glass of (?<k>.+?)'s dripping green load\.$", 'GES Bio Rifle'),
    @('^(?<k>[^>]+?) > (?<w>[^>]+?) > (?<v>[^>]+)$', $null)
)
function Get-KillMatch([string]$Text) {
    if ($Text.StartsWith('You were killed by')) { return $null }
    foreach ($p in $killPatterns) {
        if ($Text -cmatch $p[0]) {
            return @{ k = $Matches.k.Trim(); v = $Matches.v.Trim(); w = $(if ($p[1]) { $p[1] } else { $Matches.w.Trim() }) }
        }
    }
    return $null
}
$events = New-Object System.Collections.Generic.List[object]
$seen = @{}
foreach ($raw in $lines.ToArray()) {
    $d = ConvertFrom-DDLine $raw
    if (-not $d -or $d.Tag -notin 'STR', 'MSG') { continue }
    $txt = $d.Text.Trim(); $t = [math]::Round($d.t, 2)
    $key = "$t|$txt"; if ($seen[$key]) { continue }; $seen[$key] = 1
    $e = $null
    if ($txt -match '^(?<k>.+?) inflicted mortal damage upon (?<v>.+) with the (?<w>.+?)\.?$') {
        $e = @{ type = 'kill'; killer = $Matches.k; victim = $Matches.v; weapon = $Matches.w }
    } elseif ($txt -match '^(?<k>.+?) telefragged (?<v>.+?)!$') {
        $e = @{ type = 'kill'; killer = $Matches.k; victim = $Matches.v; weapon = 'telefrag' }
    } elseif ($txt -match '^(?<k>.+?) killed (?<v>.+?) with (?:a |an |the )?(?<w>.+?)\.?$') {
        $e = @{ type = 'kill'; killer = $Matches.k; victim = $Matches.v; weapon = $Matches.w }
    } elseif ($kw = Get-KillMatch $txt) {
        # other wordings (stock weapons, ComboGib, Enhanced Shock, "killer > weapon > victim"); same list as kill_messages.py
        $e = @{ type = 'kill'; killer = $kw.k; victim = $kw.v; weapon = $kw.w }
    } elseif ($txt -match '^(?<p>.+?) had an? (?<m>.+?)!+$') {
        $e = @{ type = 'multikill'; player = $Matches.p; label = ($Matches.m -replace '\s+', ' ') }
    } elseif ($txt -match '^(?<p>.+?) is (?<m>on a killing spree|on a rampage|dominating|unstoppable|godlike|wicked sick)') {
        $e = @{ type = 'spree'; player = $Matches.p; label = $Matches.m }
    } elseif ($txt -match "^(?<p>.+?)'s killing spree was ended by (?<k>.+)$") {
        $e = @{ type = 'spree_end'; player = $Matches.p; killer = $Matches.k }
    } elseif ($txt -match '^(?<p>.+?) (?<a>captured|has|dropped|returns|returned) the (?<f>red|blue) flag') {
        $e = @{ type = "flag_$($Matches.a)"; player = $Matches.p; flag = $Matches.f }
    } elseif ($txt -match '^(?<p>.+?) covered the flagcarrier') {
        $e = @{ type = 'cover'; player = $Matches.p }
    }
    if ($e) { $e.t = $t; $e.text = $txt; $events.Add([pscustomobject]$e) }
}
$players = $lines.ToArray() | ForEach-Object { ConvertFrom-DDLine $_ } | Where-Object { $_ -and $_.Tag -eq 'PLAYER' } |
    Select-Object @{n = 'name'; e = { $_.name } }, @{n = 'team'; e = { [int]$_.team } }, @{n = 'score'; e = { [int]$_.score } }, @{n = 'deaths'; e = { [int]$_.deaths } }
$result = [ordered]@{
    demo = $demoPath; length = $total; scannedAt = (Get-Date).ToString('s'); scanSpeed = $Speed
    wallSeconds = [math]::Round($sw.Elapsed.TotalSeconds, 1); speedFixes = $fixes
    players = @($players); events = $events.ToArray()
}
# raw rich lines (positions, balls, combos, shots, deaths) for tools\analyze_rich.py
$richTags = '^DemoDirector: DD\|(POS|BALLEND|COMBO|SHOT|DEATH|FLAGBASE|PID|STR|MSG)\|'
$lines.ToArray() | Where-Object { $_ -match $richTags } | ForEach-Object { $_.Substring(17) } |
    Set-Content -LiteralPath (Join-Path $outDir "$name.rich.log") -Encoding UTF8
$outFile = Join-Path $outDir "$name.events.json"
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outFile -Encoding UTF8
[pscustomobject]@{ demo = $name; length = $total; wallSec = $result.wallSeconds; events = $events.Count; kills = @($events.ToArray() | Where-Object type -eq 'kill').Count; file = $outFile }
