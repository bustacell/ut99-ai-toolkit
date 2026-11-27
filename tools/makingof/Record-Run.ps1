<#
.SYNOPSIS
  Capture helper for the making-of. Runs next to a /frag-movie session and changes nothing in UT or OBS.
  - records the desktop (the terminal) with ffmpeg whenever UT is NOT running (the game covers the screen otherwise,
    and a desktop encode next to a render would cost frames);
  - logs every command file written to <run>\runtime\cmd.txt with a wall-clock timestamp;
  - logs when UT starts and exits (wall clock of scan and render) and keeps a copy of each UnrealTournament.log.
  Stop it by creating the file <OutDir>\STOP.
.EXAMPLE
  .\Record-Run.ps1 -RunDir X:\UTDD-run -OutDir X:\UTDD\output\work\makingof\capture
#>
param(
    [Parameter(Mandatory)][string]$RunDir,
    [Parameter(Mandatory)][string]$OutDir,
    [int]$IdleBeforeRecord = 12,      # seconds without UT before the desktop recording starts
    [int]$SegmentMinutes = 30
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $OutDir, (Join-Path $OutDir 'utlogs') | Out-Null
$stopFile = Join-Path $OutDir 'STOP'
Remove-Item -LiteralPath $stopFile -ErrorAction SilentlyContinue
$timeline = Join-Path $OutDir 'timeline.csv'
$cmdLog = Join-Path $OutDir 'cmd-log.jsonl'
$cmdFile = Join-Path $RunDir 'runtime\cmd.txt'
$cfg = Get-Content -LiteralPath (Join-Path $RunDir 'config.json') -Raw | ConvertFrom-Json
$utRoot = if ([IO.Path]::IsPathRooted($cfg.utRoot)) { $cfg.utRoot } else { Join-Path $RunDir $cfg.utRoot }
$utLog = Join-Path $utRoot 'System\UnrealTournament.log'
if (-not (Test-Path -LiteralPath $timeline)) { 'time,event,detail' | Set-Content -LiteralPath $timeline -Encoding UTF8 }
function Mark([string]$ev, [string]$detail = '') { Add-Content -LiteralPath $timeline ("{0:yyyy-MM-ddTHH:mm:ss.fff},{1},{2}" -f (Get-Date), $ev, $detail) }

$ff = $null
function Start-Seg {
    $name = "term-{0:yyyyMMdd-HHmmss}.mkv" -f (Get-Date)
    $psi = [Diagnostics.ProcessStartInfo]::new('ffmpeg')
    $psi.Arguments = "-hide_banner -loglevel error -y -f lavfi -i `"ddagrab=framerate=60:draw_mouse=1,hwdownload,format=bgra`" -c:v libx264 -preset ultrafast -crf 14 -pix_fmt yuv420p `"$(Join-Path $OutDir $name)`""
    $psi.RedirectStandardInput = $true; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $script:ff = [Diagnostics.Process]::Start($psi)
    $script:segStart = Get-Date
    Mark 'terminal_record_start' $name
}
function Stop-Seg {
    if (-not $script:ff) { return }
    try { if (-not $script:ff.HasExited) { $script:ff.StandardInput.Write('q'); $script:ff.StandardInput.Flush(); [void]$script:ff.WaitForExit(8000) } } catch {}
    if (-not $script:ff.HasExited) { $script:ff.Kill() }
    $script:ff = $null
    Mark 'terminal_record_stop'
}

$lastCmd = ''; $lastCmdWrite = [datetime]::MinValue
$utPid = 0; $utSince = Get-Date; $utGone = Get-Date
Mark 'capture_start' $RunDir
try {
    while (-not (Test-Path -LiteralPath $stopFile)) {
        # --- command channel ---------------------------------------------------------
        try {
            $fi = [IO.FileInfo]::new($cmdFile)
            if ($fi.Exists -and $fi.LastWriteTimeUtc -ne $lastCmdWrite) {
                $lastCmdWrite = $fi.LastWriteTimeUtc
                $txt = [IO.File]::ReadAllText($cmdFile)
                $rec = [ordered]@{ time = $fi.LastWriteTime.ToString('yyyy-MM-ddTHH:mm:ss.fff'); commands = @($txt -split "`r?`n" | Where-Object { $_ }) }
                Add-Content -LiteralPath $cmdLog ($rec | ConvertTo-Json -Compress)
            }
        } catch {}     # file busy: the next pass reads it
        # --- UT up or down -----------------------------------------------------------
        $ut = Get-Process UnrealTournament -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($ut -and $utPid -ne $ut.Id) {
            $utPid = $ut.Id; $utSince = Get-Date
            Stop-Seg
            Mark 'ut_start' "pid=$utPid"
        } elseif (-not $ut -and $utPid) {
            $utGone = Get-Date
            $copy = Join-Path $OutDir ("utlogs\ut-{0:yyyyMMdd-HHmmss}.log" -f $utSince)
            try { Copy-Item -LiteralPath $utLog -Destination $copy -Force } catch {}
            Mark 'ut_exit' "pid=$utPid"
            $utPid = 0
        }
        if (-not $ut -and -not $ff -and ((Get-Date) - $utGone).TotalSeconds -ge $IdleBeforeRecord) { Start-Seg }
        if ($ff -and ((Get-Date) - $segStart).TotalMinutes -ge $SegmentMinutes) { Stop-Seg }     # roll over
        if ($ff -and $ff.HasExited) { Mark 'terminal_record_died' "exit=$($ff.ExitCode)"; $ff = $null; $utGone = Get-Date }
        Start-Sleep -Milliseconds 15
    }
} finally {
    Stop-Seg
    Mark 'capture_stop'
}
