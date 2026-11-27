# Timedemo a demo (read-only): plays it with `timedemo 1`; when the demo ends (or is stopped after -MaxSec) the
# log gets "N frames rendered in S seconds. Min/Max/Avg fps". Prints that summary.
# The client's FrameRateLimit ([WinDrv.WindowsClient]) caps the result; uncap it (with a backup) to see headroom.
# Usage: Timedemo.ps1 <demo.dem> [-MaxSec 400]
param([Parameter(Mandatory)][string]$Demo, [int]$MaxSec = 400)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
$sys = Join-Path $DDUT 'System'
$log = Join-Path $sys 'UnrealTournament.log'
if (Get-UTProcess) { Stop-UT }
$rel = [IO.Path]::GetRelativePath($sys, (Resolve-Path -LiteralPath $Demo).Path)
$exec = Join-Path $env:TEMP 'dd-timedemo.txt'
Set-Content $exec "ddautoclose 1`r`ntimedemo 1`r`ndemoplay $rel" -Encoding Ascii
$p = Start-Process (Join-Path $sys 'UnrealTournament.exe') -WorkingDirectory $sys -PassThru `
    -ArgumentList "-exec=$exec", '-FORCELOGFLUSH'
Register-UTProcess $p                  # ours: Stop-UT may close it later
$sw = [Diagnostics.Stopwatch]::StartNew()
Start-Sleep 5
while ($sw.Elapsed.TotalSeconds -lt $MaxSec) {
    $p.Refresh()
    if ($p.HasExited) { break }
    if ($p.MainWindowTitle -like '*Recovery Mode*') { [void](Invoke-UTRecoveryDialog $p) }
    if (Select-String -LiteralPath $log -Pattern '^ScriptLog: \d{3,} frames rendered' -Quiet) { break }
    Start-Sleep 2
}
# cut long demos: stopping the demo makes timedemo print its summary
if (-not (Select-String -LiteralPath $log -Pattern '^ScriptLog: \d{3,} frames rendered' -Quiet)) {
    Send-UTCommand 'stopdemo' -SettleMs 3000
}
"wall {0:N0} s" -f $sw.Elapsed.TotalSeconds
$fps = Select-String -LiteralPath $log -Pattern '^ScriptLog: \d+ frames rendered' | ForEach-Object Line
"{0} status lines" -f $fps.Count
$fps | Select-Object -Last 3
Select-String -LiteralPath $log -Pattern 'stopped \(|ended:|Bringing Level CTF' | Select-Object -Last 3 | ForEach-Object Line
Stop-UT
