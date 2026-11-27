# Playtest a generated map: CTF with bots, no cap/time limit, three screenshots (System\Screenshots), log summary.
# The game owns the screen while this runs.
# -Mutator: default stock instagib (beam only; closest bot proxy for ComboGib). '' = standard weapons.
# -Record: writes recordings\mapgen\<Map>-bots.dem (scan it with Scan-Demo, then MOVE the scan files out of
#          output\scans into output\mapgen\scans: archive tools read everything in output\scans).
param([string]$Map = 'CTF-DDTest', [int]$Bots = 4, [int]$Seconds = 60,
      [string]$Mutator = 'Botpack.InstaGibDM', [switch]$Record, [int]$BotSkill = 5)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
$sys = Join-Path $DDUT 'System'
if (Get-UTProcess) { Stop-UT }
Sync-UTBinding
$log = Join-Path $sys 'UnrealTournament.log'
# join as a real player (a User.ini OverrideClass spectator can't start the match: offline games wait for Fire)
$url = "${Map}?Game=Botpack.CTFGame?GoalTeamScore=0?TimeLimit=0?Difficulty=$BotSkill" +
       "?OverrideClass=Botpack.TMale1?Class=Botpack.TMale1?Team=0"
# Team=0: new bots join the smaller team, ties go to red. With the (dead) player on red, 8 bots end up 4+player vs 4,
# i.e. 4 vs 4 active; on blue (User.ini team=1) they ended up 5 vs 3.
if ($Mutator) { $url += "?Mutator=$Mutator" }
$p = Start-Process (Join-Path $sys 'UnrealTournament.exe') -ArgumentList $url, '-FORCELOGFLUSH' -WorkingDirectory $sys -PassThru
Register-UTProcess $p                  # ours: Stop-UT may close it later
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 60) {
    $p.Refresh()
    if ($p.HasExited) { throw 'UT exited during startup' }
    if ($p.MainWindowTitle -like '*Recovery Mode*') { [void](Invoke-UTRecoveryDialog $p); Start-Sleep 2; continue }
    if ((Test-Path $log) -and (Select-String -LiteralPath $log -Pattern "Bringing Level $Map" -Quiet)) { break }
    Start-Sleep 1
}
Start-Sleep 4
# GameSpeed comes from the ini, where a demo scan's slomo may have been saved (16-32x): force normal speed
Send-UTCommand 'slomo 1' -SettleMs 300
Send-UTCommand "addbots $Bots" -SettleMs 1000
# start the match like a player would (Fire), then leave it: suicide and stay dead, so only bots play and only bot
# positions end up in the scan. (At the old saved 32x game speed the wait was skipped, which hid this.)
Send-UTCommand 'fire' -SettleMs 1500
Send-UTCommand 'suicide' -SettleMs 500
Start-Sleep 3
if ($Record) {
    $recDir = Join-Path $PSScriptRoot '..\..\recordings\mapgen'
    New-Item -ItemType Directory -Force $recDir | Out-Null
    $demo = Join-Path (Resolve-Path $recDir).Path "$Map-bots.dem"
    Send-UTCommand ("demorec " + ([IO.Path]::GetRelativePath($sys, $demo) -replace '\.dem$', '')) -SettleMs 500
}
Send-UTCommand 'behindview 1', 'viewclass Bot' -SettleMs 300
Start-Sleep ([math]::Max(5, $Seconds - 15))
Send-UTCommand 'shot' -SettleMs 1500
Send-UTCommand 'viewclass Bot' -SettleMs 800
Send-UTCommand 'shot' -SettleMs 1500
Start-Sleep 8
Send-UTCommand 'viewself', 'shot' -SettleMs 1500
if ($Record) { Send-UTCommand 'stopdemo' -SettleMs 1500; "demo: $demo" }
Stop-UT
Select-String -LiteralPath $log -Pattern 'Critical|Error|flag|Bringing|Bot|accessed none' | Select-Object -Last 40 | ForEach-Object Line
Get-ChildItem (Join-Path $sys 'Screenshots') -Filter 'Shot*' | Where-Object LastWriteTime -gt (Get-Date).AddMinutes(-3) | ForEach-Object FullName
