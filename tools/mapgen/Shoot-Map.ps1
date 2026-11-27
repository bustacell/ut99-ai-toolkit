# Beauty shots of a generated map at exact camera positions.
#  1. Records a short spectator demo on the map (once per map build; -Rerecord forces it).
#  2. Plays the demo back and places DDCam (mode=static) at each shot of the JSON list
#     [{ "name": "...", "p": [x,y,z], "at": [x,y,z], "fov": 90 }, ...], one screenshot per shot.
# Prints "<name>`t<screenshot path>" per shot. The game owns the screen while this runs.
# -FromDemo <path>: shoot inside an existing demo instead (reference shots of other maps); -Map is then only a label.
# -DemoTime <s>: wait this long after the demo starts before the first shot (players spread out).
param([Parameter(Mandatory)][string]$Map, [Parameter(Mandatory)][string]$Shots, [int]$RecordSec = 50,
      [int]$Bots = 0, [switch]$Rerecord, [string]$FromDemo, [int]$DemoTime = 0)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
$sys = Join-Path $DDUT 'System'
$shotDir = Join-Path $sys 'Screenshots'
$log = Join-Path $sys 'UnrealTournament.log'
$list = Get-Content -LiteralPath $Shots -Raw | ConvertFrom-Json
$recDir = Join-Path $PSScriptRoot '..\..\recordings\mapgen'
New-Item -ItemType Directory -Force $recDir | Out-Null
$demo = Join-Path (Resolve-Path $recDir).Path "$Map-shoot.dem"
$mapFile = Join-Path $DDUT "Maps\$Map.unr"
if ($FromDemo) { $demo = Resolve-DDDemo $FromDemo }

if (-not $FromDemo -and ($Rerecord -or -not (Test-Path -LiteralPath $demo) -or
    (Get-Item -LiteralPath $demo).LastWriteTime -lt (Get-Item -LiteralPath $mapFile).LastWriteTime)) {
    if (Get-UTProcess) { Stop-UT }
    Sync-UTBinding
    $recStart = Get-Date
    $p = Start-Process (Join-Path $sys 'UnrealTournament.exe') -WorkingDirectory $sys -PassThru `
        -ArgumentList "${Map}?Game=Botpack.CTFGame?GoalTeamScore=0?TimeLimit=0", '-FORCELOGFLUSH'
    Register-UTProcess $p              # ours: Stop-UT may close it later
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        if ($sw.Elapsed.TotalSeconds -gt 60) { throw 'map did not load' }
        $p.Refresh()
        if ($p.HasExited) { throw 'UT exited during startup' }
        if ($p.MainWindowTitle -like '*Recovery Mode*') { [void](Invoke-UTRecoveryDialog $p); Start-Sleep 2; continue }
        # only this session's log counts: the previous session's log can already hold "Bringing Level <map>"
        # (from playing a demo of the same map), and then demorec was sent before the map had loaded
        if ((Test-Path $log) -and (Get-Item -LiteralPath $log).LastWriteTime -ge $recStart -and
            (Select-String -LiteralPath $log -Pattern "Bringing Level $Map" -Quiet)) { break }
        Start-Sleep 1
    }
    Start-Sleep 4
    Send-UTCommand 'slomo 1' -SettleMs 300      # GameSpeed may hold a scan's saved slomo (see Playtest-Map.ps1)
    if ($Bots) { Send-UTCommand "addbots $Bots" -SettleMs 2000 }
    # demorec takes a name relative to System; keep the file out of UT\Demos
    $rel = [IO.Path]::GetRelativePath($sys, $demo) -replace '\.dem$', ''
    Send-UTCommand "demorec $rel" -SettleMs 500
    Start-Sleep $RecordSec
    Send-UTCommand 'stopdemo' -SettleMs 1500
    Stop-UT
    if (-not (Test-Path -LiteralPath $demo) -or (Get-Item -LiteralPath $demo).LastWriteTime -lt $recStart) {
        throw "demo was not (re)written to $demo"      # an old demo of a previous build fails with "missing packages"
    }
}

$before = @(Get-ChildItem $shotDir -Filter 'Shot*' -ErrorAction SilentlyContinue | ForEach-Object Name)
[void](Start-UTDemo $demo)
Send-UTCommand 'ddhud 0' -SettleMs 300
if ($DemoTime) { Start-Sleep $DemoTime }
$names = @()
foreach ($s in $list) {
    $fov = if ($s.fov) { $s.fov } else { 90 }
    # invariant culture: on a German/French Windows "-f" writes 800,2 for 800.2 and the camera gets garbage
    $camCmd = [string]::Format([Globalization.CultureInfo]::InvariantCulture,
        'ddcam mode=static p={0},{1},{2} at={3},{4},{5} fov={6}', [object[]]($s.p + $s.at + $fov))
    Send-UTCommand $camCmd -SettleMs 1300
    if ($s.cmd) { Send-UTCommand $s.cmd -SettleMs 600 }      # optional per-shot console command (e.g. "rmode 6")
    Send-UTCommand 'shot' -SettleMs 900
    $names += $s.name
}
Stop-UT
$new = @(Get-ChildItem $shotDir -Filter 'Shot*' | Where-Object { $before -notcontains $_.Name } | Sort-Object Name)
for ($i = 0; $i -lt $new.Count; $i++) { "{0}`t{1}" -f $names[$i], $new[$i].FullName }
