<#
.SYNOPSIS
  Wait until the /frag-movie session in the run folder is idle (waiting for an answer or finished), then print
  its last message and exit. Reads the session's own transcript file; changes nothing.
  Idle = transcript not written for -IdleSeconds, UT not running, no python/ffmpeg/pwsh job of the run active.
.EXAMPLE
  .\Watch-Run.ps1 -RunDir X:\UTDD-run
#>
param(
    [Parameter(Mandatory)][string]$RunDir,
    [int]$IdleSeconds = 75,
    [int]$MaxHours = 10
)
$ErrorActionPreference = 'Stop'
$proj = Join-Path $env:USERPROFILE ('.claude\projects\' + ($RunDir -replace '[:\\/]', '-'))
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalHours -lt $MaxHours) {
    Start-Sleep -Seconds 10
    $f = Get-ChildItem -LiteralPath $proj -Filter *.jsonl -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $f) { continue }
    if (((Get-Date) - $f.LastWriteTime).TotalSeconds -lt $IdleSeconds) { continue }
    if (Get-Process UnrealTournament -ErrorAction SilentlyContinue) { continue }
    $busy = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='ffmpeg.exe' OR Name='ucc.exe'" |
        Where-Object { $_.CommandLine -notmatch 'ddagrab' -and $_.CommandLine -match [regex]::Escape($RunDir) }
    if ($busy) { continue }
    # last assistant text in the transcript
    $text = ''; $pending = ''
    foreach ($l in (Get-Content -LiteralPath $f.FullName -Tail 60)) {
        try { $o = $l | ConvertFrom-Json } catch { continue }
        if ($o.type -eq 'assistant' -and $o.message.content) {
            foreach ($c in $o.message.content) {
                if ($c.type -eq 'text' -and $c.text) { $text = $c.text; $pending = '' }
                if ($c.type -eq 'tool_use') { $pending = "$($c.name): " + (($c.input | ConvertTo-Json -Depth 6 -Compress) -replace '\s+', ' ') }
            }
        } elseif ($o.type -eq 'user') { $pending = '' }
    }
    "IDLE at $(Get-Date -Format s), transcript $($f.Name), last write $($f.LastWriteTime.ToString('HH:mm:ss'))"
    '--- last message ---'
    if ($text.Length -gt 2500) { $text.Substring($text.Length - 2500) } else { $text }
    if ($pending) { '--- open tool call ---'; if ($pending.Length -gt 2500) { $pending.Substring(0, 2500) } else { $pending } }
    exit 0
}
'TIMEOUT'
