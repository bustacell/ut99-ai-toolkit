<#
.SYNOPSIS
  Render a segment of a UT99 demo to MP4.
.EXAMPLE
  .\Render-Clip.ps1 -Demo CTF-2on2-Crates2022_03-07_00-43-36.dem -Start 2:35 -Duration 15 -Player YourNick -Camera first
.NOTES
  Start/End are demo time (seconds since demo start, uDemo "SeekTo" semantics), "ss", "m:ss" or "h:mm:ss".
  Camera: first | behind | free | recorder.  Speed < 1 records slow motion (in-engine, real time capture).
#>
param(
    [Parameter(Mandatory)][string]$Demo,
    [Parameter(Mandatory)][string]$Start,
    [double]$Duration = 0,
    [string]$End,
    [string]$Player,
    [ValidateSet('first', 'behind', 'free', 'recorder', 'cam')][string]$Camera = 'first',
    [string]$Cam,                 # ddcam arguments for -Camera cam (tgt/look/ballby may be player NAMES via tgtname=, lookname=)
    [string]$TakeFile,            # one-take rig timeline for -Camera cam: one "start=<demo s> blend=<s> [whip=<deg>] <ddcam args>" per line (docs\ONETAKE.md)
    [double]$Speed = 1.0,
    [string]$Ramp,                # speed keyframes in demo time "t:s,t:s,..." (exponential between); overrides -Speed
    [string]$Type,                # ddtype arguments, e.g. "dt0=57.4 cps=9 hold=0.6 text=slomo 0" (cosmetic console typing)
    [string]$Bullet,              # ddbullet arguments (bullet-time sniper bullet + exploding head), see DDBullet.uc / docs\HEADSHOT.md
    [string[]]$Exec,              # extra console commands sent with the camera setup (before recording)
    [switch]$HideHud,
    [ValidateSet(-1, 0, 1, 2, 3)][int]$HudMode = -1,   # 0 original, 1 cinematic, 2 blank, 3 crosshair + name tags only (-1: from -HideHud)
    [switch]$NoGore,
    [switch]$ClearDecals,         # remove decals piled up during the seek (blood builds up again during the clip)
    [string[]]$Tags,              # player names that get a name tag in cam shots
    [string]$Output,
    [double]$PreRoll = 2.0,
    [switch]$KeepRaw,
    [switch]$KeepGameOpen,
    [switch]$Reuse   # reuse an already running UT with the same demo loaded
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'OBSWebSocket.psm1') -Force

function ConvertTo-Seconds([string]$s) {
    $parts = $s.Split(':'); $t = 0.0
    foreach ($p in $parts) { $t = $t * 60 + [double]::Parse($p, $inv) }
    return $t
}
function F([double]$x) { $x.ToString('0.###', $inv) }

# --- speed ramp (same math as DDWatcher.WallBetween) -----------------------------------
$rk = @()
if ($Ramp) {
    foreach ($p in $Ramp.Split(',')) {
        $ts = $p.Split(':')
        $rk += [pscustomobject]@{ t = [double]::Parse($ts[0], $inv); s = [math]::Max(0.001, [double]::Parse($ts[1], $inv)) }
    }
    for ($i = 1; $i -lt $rk.Count; $i++) { if ($rk[$i].t -le $rk[$i - 1].t) { throw 'Ramp keyframes must ascend in time' } }
    if ($rk.Count -lt 1 -or $rk.Count -gt 8) { throw 'Ramp needs 1 to 8 keyframes' }
    $Speed = $rk[0].s
}
function SpeedAt([double]$t) {
    if (-not $rk) { return $Speed }
    if ($t -le $rk[0].t) { return $rk[0].s }
    for ($i = 0; $i -lt $rk.Count - 1; $i++) {
        if ($t -lt $rk[$i + 1].t) { $u = ($t - $rk[$i].t) / ($rk[$i + 1].t - $rk[$i].t); return $rk[$i].s * [math]::Exp($u * [math]::Log($rk[$i + 1].s / $rk[$i].s)) }
    }
    return $rk[-1].s
}
function SegWall([double]$a, [double]$b, $k0, $k1) {
    if ($b -le $a) { return 0.0 }
    $L = $k1.t - $k0.t; $lr = [math]::Log($k1.s / $k0.s)
    if ([math]::Abs($lr) -lt 0.0001) { return ($b - $a) / $k0.s }
    $ua = ($a - $k0.t) / $L; $ub = ($b - $k0.t) / $L
    return $L / ($k0.s * $lr) * ([math]::Exp(-$ua * $lr) - [math]::Exp(-$ub * $lr))
}
function WallBetween([double]$a, [double]$b) {
    if ($b -le $a) { return 0.0 }
    if (-not $rk) { return ($b - $a) / $Speed }
    $w = 0.0
    if ($a -lt $rk[0].t) { $w += ([math]::Min($b, $rk[0].t) - $a) / $rk[0].s }
    for ($i = 0; $i -lt $rk.Count - 1; $i++) { $w += SegWall ([math]::Max($a, $rk[$i].t)) ([math]::Min($b, $rk[$i + 1].t)) $rk[$i] $rk[$i + 1] }
    if ($b -gt $rk[-1].t) { $w += ($b - [math]::Max($a, $rk[-1].t)) / $rk[-1].s }
    return $w
}

$root = $DDRoot
$demoPath = Resolve-DDDemo $Demo
if (-not (Test-Path -LiteralPath $demoPath)) { throw "Demo not found: $Demo" }
$t0 = ConvertTo-Seconds $Start
$t1 = if ($End) { ConvertTo-Seconds $End } elseif ($Duration -gt 0) { $t0 + $Duration } else { throw 'Give -Duration or -End' }
if ($t1 -le $t0) { throw 'End must be after Start' }
if ($Speed -le 0 -or $Speed -gt 4) { throw 'Speed must be in (0, 4]' }
if ($Player -and $Player -match '[\r\n"]') { throw 'Invalid player name' }
if (-not $Output) {
    $base = [IO.Path]::GetFileNameWithoutExtension($demoPath)
    $Output = Join-Path "$root\output" ("{0}_{1}-{2}_{3}{4}.mp4" -f $base, [int]$t0, [int]$t1, $Camera, $(if ($Speed -ne 1) { "_x$(F $Speed)" } else { '' }))
}
$ffmpeg = (Get-Command ffmpeg).Source
$ffprobe = Join-Path (Split-Path $ffmpeg) 'ffprobe.exe'
$report = [ordered]@{ demo = $demoPath; start = $t0; end = $t1; camera = $Camera; player = $Player; speed = $Speed }
if ($Ramp) { $report.ramp = $Ramp }

# --- OBS ---------------------------------------------------------------------
# take the job lock BEFORE touching OBS or UT: another job may be recording right now (fails fast, names the holder)
Enter-DDJob
Set-UTKeepAwake
Start-OBSApp
Confirm-OBSCrashDialog
Connect-OBS -TimeoutSec 60 | Out-Null
# a freshly started OBS answers 207 "not ready" for a few seconds: wait instead of failing
for ($try = 1; ; $try++) {
    try { $rs = Invoke-OBS GetRecordStatus; break }
    catch { if ($_.Exception.Message -notmatch '207' -or $try -ge 30) { throw }; Start-Sleep 1 }
}
if ($rs.outputActive) { Invoke-OBS StopRecord | Out-Null; Start-Sleep 2 }
$rawDir = "$root\recordings"
New-Item -ItemType Directory -Force $rawDir | Out-Null   # OBS silently refuses to record into a missing folder
Invoke-OBS SetRecordDirectory @{ recordDirectory = $rawDir.Replace('\', '/') } | Out-Null

# --- UT: load demo -------------------------------------------------------------
$running = Get-UTProcess
if ($Reuse -and $running) { Reset-UTLogCursor } else { [void](Start-UTDemo $demoPath) ; Start-Sleep 1 }
$st = Get-UTStatus
if (-not $st) { throw 'No status from DemoDirector helper (is the demo playing?)' }
$total = [double]::Parse($st.total, $inv)
$report.demoLength = $total
if ($t0 -ge $total) { throw "Start $t0 is beyond demo length $total" }
if ($t1 -gt $total) { $t1 = $total; $report.end = $t1; $report.note = 'end clamped to demo length' }

# --- seek to pre-roll point, pause, set up camera --------------------------------
$seekT = [math]::Max(0, $t0 - $PreRoll * $Speed)
if ($st.paused -ne '0') { Send-UTCommand 'pause' }
Send-UTCommand 'setpausetext hide' -SettleMs 50
# seek and pause; if the seek landed after the clip start, seek again further back
for ($attempt = 1; $attempt -le 3; $attempt++) {
    $seek = Invoke-UTSeek $seekT
    Send-UTCommand 'pause'
    Start-Sleep -Milliseconds 300
    $chk = Get-UTStatus
    if ($chk.t -le $t0 - 0.05 -or $t0 -lt 0.2) { break }
    Send-UTCommand 'pause' -SettleMs 100
    $seekT = [math]::Max(0, $seekT - 1.0 * $attempt)
    Write-Warning "seek landed at $($chk.t) (after start $t0); retrying at $seekT"
}
$report.seek = $seek
$cmds = @()
# Client demos lock the camera to the recorder (uDemo bLockOn); "spectate" unlocks it,
# "firstperson" re-locks to the recorder (smoothest first-person view of the recorder).
$recorder = $st.linked
switch ($Camera) {
    'first' {
        if (-not $Player) { throw '-Player required for first' }
        if ($recorder -and $Player -eq $recorder) { $cmds += 'firstperson', 'behindview 0' }
        else { $cmds += 'spectate', "viewplayer $Player", 'behindview 0' }
    }
    'behind'   { if (-not $Player) { throw '-Player required for behind' }; $cmds += 'spectate', "viewplayer $Player", 'behindview 1' }
    'free'     { $cmds += 'spectate', 'viewself' }
    'recorder' { $cmds += 'firstperson', 'behindview 0' }
    'cam' {
        if (-not $Cam -and -not $TakeFile) { throw '-Cam or -TakeFile required for -Camera cam' }
        # player names -> PlayerIDs (tgtname=, lookname=, ballbyname=)
        $ids = @{}; foreach ($pl in (Get-UTPlayers)) { if ($pl.spec -ne 'True' -or -not $ids.ContainsKey($pl.name)) { $ids[$pl.name] = $pl.id } }
        $resolve = {
            param([string]$a)
            foreach ($key in 'tgt', 'look', 'ballby') {
                if ($a -match "(^| )$($key)name=(\S+)") {
                    $nm = [uri]::UnescapeDataString($Matches[2])
                    if (-not $ids.ContainsKey($nm)) { throw "Player '$nm' not found in demo" }
                    $a = $a -replace "(^| )$($key)name=\S+", "`$1$key=$($ids[$nm])"
                }
            }
            $a
        }
        $cmds += 'spectate', 'viewself', 'behindview 0'
        if ($TakeFile) {
            # one take: every non-comment line is a DDCam rig (see DDTake.uc)
            $rigs = @(Get-Content -LiteralPath $TakeFile | Where-Object { $_.Trim() -and -not $_.TrimStart().StartsWith('#') } | ForEach-Object { & $resolve $_.Trim() })
            $cmds += 'ddcam mode=off', 'ddtake clear'
            $cmds += $rigs | ForEach-Object { "ddtake add $_" }
            $cmds += 'ddtake go'
            $report.take = $TakeFile; $report.rigs = $rigs.Count
        } else {
            $camArgs = & $resolve $Cam
            $cmds += "ddcam $camArgs dt0=$(F $t0)"
            $report.camArgs = "$camArgs dt0=$(F $t0)"
        }
    }
}
$tagIds = @()
if ($Tags) {
    if (-not $ids) { $ids = @{}; foreach ($pl in (Get-UTPlayers)) { if (-not $ids.ContainsKey($pl.name)) { $ids[$pl.name] = $pl.id } } }
    foreach ($nm in $Tags) { if ($ids.ContainsKey($nm)) { $tagIds += $ids[$nm] } }
}
$cmds += "ddtag $($tagIds -join ' ')"
$cmds += "ddnogore $(if ($NoGore) { '1' } else { '0' })"
if ($ClearDecals) { $cmds += 'dddecals' }
$cmds += "slomo $(F $Speed)"
$cmds += $(if ($Ramp) { "ddramp $Ramp" } else { 'ddramp off' })
$cmds += $(if ($Type) { "ddtype $Type" } else { 'ddtype off' })
$cmds += $(if ($Bullet) { "ddbullet $Bullet" } else { 'ddbullet off' })
if ($Bullet) { $report.bullet = $Bullet }
if ($Exec) { $cmds += $Exec }
if ($HudMode -lt 0) { $HudMode = $(if ($HideHud) { 2 } else { 0 }) }
$cmds += "ddhudmode $HudMode"
Send-UTCommand $cmds -SettleMs 400
$st = Get-UTStatus
if ($st.paused -eq '0') { throw 'Demo is not paused before recording' }
if ($Player -and $Camera -in 'first', 'behind' -and $st.view -ne $Player) { throw "Camera is on '$($st.view)', expected '$Player'" }
if ($Camera -eq 'behind' -and $st.behind -ne 'True') { throw 'Behind view did not engage' }
if ($Camera -eq 'first' -and $st.behind -ne 'False') { throw 'First person view did not engage' }
if ($Camera -eq 'cam' -and $st.view -ne '') { throw "Free camera did not engage (view=$($st.view))" }
$pausedT = $st.t
$report.view = $st.view; $report.behind = $st.behind

# --- record ------------------------------------------------------------------------
# live capture check: a stale game-capture hook delivers black frames -> restart OBS once
$capLuma = Get-OBSSourceLuma
if ($capLuma -lt 6) {
    Write-Warning "OBS capture is black (luma $([math]::Round($capLuma,1))); restarting OBS"
    Restart-OBSApp
    Start-Sleep 4
    $capLuma = Get-OBSSourceLuma
    if ($capLuma -lt 6) { throw "OBS capture still black after restart (luma $capLuma)" }
}
$report.captureLuma = [math]::Round($capLuma, 1)
Clear-OBSEvents
Invoke-OBS StartRecord | Out-Null
[void](Wait-OBSEvent RecordStateChanged { param($d) $d.outputState -eq 'OBS_WEBSOCKET_OUTPUT_STARTED' } 20)
Start-Sleep -Milliseconds 800
$videoAtUnpause = (Invoke-OBS GetRecordStatus).outputDuration / 1000.0
Send-UTCommand 'pause', 'ddmark rec_unpause' -SettleMs 0
$wallLimit = [Diagnostics.Stopwatch]::StartNew()
$maxWall = (WallBetween $pausedT $t1) + 30
while ($true) {
    Start-Sleep -Milliseconds 400
    Set-UTKeepAwake
    $s2 = Get-UTStatus
    if ($s2 -and $s2.t -ge $t1 + 0.5 * (SpeedAt $t1)) { break }
    if ($s2 -and $s2.t -ge $total - 0.05) { break }
    if ($wallLimit.Elapsed.TotalSeconds -gt $maxWall) { throw 'Playback did not reach end time in expected wall time' }
}
# measure the real playback rate (demo seconds per video second) over the recording
$videoAtEnd = (Invoke-OBS GetRecordStatus).outputDuration / 1000.0
$demoAtEnd = (Get-UTStatus).t
$rate = ($demoAtEnd - $pausedT) / ($videoAtEnd - $videoAtUnpause)
$report.measuredRate = [math]::Round($rate, 4)
# wall scale: real video seconds per predicted wall second (1.0 = playback followed the requested speed/ramp)
$wallScale = ($videoAtEnd - $videoAtUnpause) / (WallBetween $pausedT $demoAtEnd)
$report.wallScale = [math]::Round($wallScale, 4)
if ([math]::Abs($wallScale - 1) -gt 0.05) { Write-Warning "Playback ran at $([math]::Round(1 / $wallScale, 3))x of the requested speed/ramp" }
$stop = Invoke-OBS StopRecord
if ($Camera -eq 'cam') { Send-UTCommand 'ddcam mode=off', 'ddtake off' -SettleMs 0 }
[void](Wait-OBSEvent RecordStateChanged { param($d) $d.outputState -eq 'OBS_WEBSOCKET_OUTPUT_STOPPED' } 30)
$raw = $stop.outputPath
if (-not $KeepGameOpen) { Stop-UT }
# make sure the file is finalized (not locked)
for ($i = 0; $i -lt 50; $i++) { try { [IO.File]::Open($raw, 'Open', 'Read', 'None').Dispose(); break } catch { Start-Sleep -Milliseconds 200 } }
$report.raw = $raw

# --- trim / encode -----------------------------------------------------------------
$ss = $videoAtUnpause + $wallScale * (WallBetween $pausedT $t0)
$len = $wallScale * (WallBetween $t0 $t1)
$report.trimStart = [math]::Round($ss, 3); $report.clipLength = [math]::Round($len, 3)
New-Item -ItemType Directory -Force (Split-Path $Output) | Out-Null
& $ffmpeg -hide_banner -loglevel error -y -i $raw -ss (F $ss) -t (F $len) -map 0:v:0 -map '0:a:0?' -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 60 -c:a aac -b:a 192k -movflags +faststart $Output
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed ($LASTEXITCODE)" }

# --- validate -----------------------------------------------------------------------
$probe = & $ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate -of json $Output | ConvertFrom-Json
$v = $probe.streams | Where-Object codec_type -eq 'video' | Select-Object -First 1
$a = $probe.streams | Where-Object codec_type -eq 'audio' | Select-Object -First 1
$dur = [double]::Parse($probe.format.duration, $inv)
$report.output = $Output
$report.probe = [ordered]@{ duration = $dur; width = $v.width; height = $v.height; fps = $v.avg_frame_rate; video = $v.codec_name; audio = $(if ($a) { $a.codec_name } else { 'none' }) }
# black-capture check (display off / locked screen records black): mean luma of sampled frames
$yavg = & $ffmpeg -hide_banner -i $Output -vf 'fps=2,scale=320:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG' -an -f null - 2>&1 |
    Select-String 'YAVG=([\d\.]+)' | ForEach-Object { [double]::Parse($_.Matches[0].Groups[1].Value, $inv) }
$luma = if ($yavg) { ($yavg | Measure-Object -Average).Average } else { 0 }
$report.meanLuma = [math]::Round($luma, 1)
$ok = ((($v.width -eq 1920 -and $v.height -eq 1080) -or ($v.width -eq 3840 -and $v.height -eq 2160)) -and [math]::Abs($dur - $len) -lt 0.2 -and $luma -gt 22)
if ($luma -le 22) { Write-Warning "clip looks black (mean luma $luma) - display off or capture failed?" }
$report.valid = $ok
if (-not $KeepRaw) { Remove-Item -LiteralPath $raw }
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($Output, '.json')) -Encoding UTF8
[pscustomobject]$report
if (-not $ok) { throw 'Output validation failed' }
