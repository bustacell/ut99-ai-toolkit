# FPS per viewpoint: play a demo, park DDCam (static) at each shot of a shots JSON, timedemo for a few seconds,
# read the summary line (toggling `timedemo 0` prints it). Same shots JSON as Shoot-Map.ps1; `at` must be in open
# air. Fixed views isolate the map's own cost from what a demo's moving view accumulates (see docs/MAPGEN.md).
# Usage: Fps-Spots.ps1 <demo.dem> <shots.json> [-Sec 6]
param([Parameter(Mandatory)][string]$Demo, [Parameter(Mandatory)][string]$Shots, [int]$Sec = 6)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
$log = Join-Path $DDUT 'System\UnrealTournament.log'
$list = Get-Content -LiteralPath $Shots -Raw | ConvertFrom-Json
[void](Start-UTDemo $Demo)
Send-UTCommand 'ddhud 0' -SettleMs 300
Start-Sleep 4
foreach ($s in $list) {
    $fov = if ($s.fov) { $s.fov } else { 90 }
    Send-UTCommand ("ddcam mode=static p={0},{1},{2} at={3},{4},{5} fov={6}" -f ($s.p + $s.at + $fov)) -SettleMs 1000
    $n0 = @(Select-String -LiteralPath $log -Pattern '^ScriptLog: \d+ frames rendered').Count
    Send-UTCommand 'timedemo 1' -SettleMs 200
    Start-Sleep $Sec
    Send-UTCommand 'timedemo 0' -SettleMs 1200
    $lines = @(Select-String -LiteralPath $log -Pattern '^ScriptLog: \d+ frames rendered' | ForEach-Object Line)
    $l = if ($lines.Count -gt $n0) { $lines[-1] -replace '^ScriptLog: ', '' } else { '(no summary)' }
    "{0,-26} {1}" -f $s.name, $l
}
Stop-UT
