<#
.SYNOPSIS
  Frame-stepped render of a camera path (DDCam mode=path) inside a paused demo: every output frame is rendered at
  its exact path time and saved with "shot", then assembled into a 60 fps video. Motion is exactly even whatever
  the game's frame rate, and nothing depends on the demo clock (an empty-map demo advances its clock in jumps, so a
  live capture of a path moved in bursts: ~20 frames of motion, ~20 frozen).
.EXAMPLE
  .\Render-Path.ps1 -Demo C:\x\CTF-DDLumenFilm-shoot.dem -Keys reveal.ddpath.txt -Seconds 18.6 -Output reveal.mp4
.NOTES
  For static scenes only (empty maps, flythroughs): the demo is paused, so players, flags and animated meshes do
  not move. The game window size is the frame size (Set-UTVideoMode.ps1). The game owns the screen while it runs.
#>
param([Parameter(Mandatory)][string]$Demo, [Parameter(Mandatory)][string]$Keys,
      [Parameter(Mandatory)][double]$Seconds, [Parameter(Mandatory)][string]$Output,
      [int]$Fps = 60, [double]$Kdt = 0.1, [double]$DemoTime = 3, [int]$Crf = 12, [switch]$KeepFrames,
      [int]$TimeoutSec = 0)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
$inv = [Globalization.CultureInfo]::InvariantCulture
function F([double]$x) { $x.ToString('0.#####', $inv) }
$sys = Join-Path $DDUT 'System'
$shotDir = Join-Path $sys 'Screenshots'
$keyLines = @(Get-Content -LiteralPath $Keys | Where-Object { $_.Trim() })
$expected = [int][Math]::Floor($Seconds * $Fps + 0.5) + 1      # DDCam stops once StepT > to + dt/2
if (-not $TimeoutSec) { $TimeoutSec = [int](120 + $expected * 1.5) }
$before = @{}
Get-ChildItem $shotDir -Filter 'Shot*' -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Name] = 1 }

[void](Start-UTDemo $Demo)
Start-Sleep -Seconds $DemoTime
Send-UTCommand 'pause' -SettleMs 300
Send-UTCommand 'setpausetext hide', 'ddhud 0' -SettleMs 300
Reset-UTLogCursor
Send-UTCommand $keyLines -SettleMs 800
Send-UTCommand ("ddcam mode=path kdt={0}" -f (F $Kdt)) -SettleMs 500
Send-UTCommand ("ddpath render fps={0} from=0 to={1} wait=4" -f $Fps, (F $Seconds)) -SettleMs 0
$done = Wait-UTLog -Pattern 'DD\|PATH\|.*render done' -TimeoutSec $TimeoutSec   # line: DD|PATH|t=..|render done|..
if (-not $done) { throw "render did not finish within $TimeoutSec s" }
Start-Sleep -Seconds 2                                  # last PNG written
Send-UTCommand 'ddcam mode=off' -SettleMs 200
Stop-UT                       # a running UT holds the map file: a following Build-Map could not replace it

$shots = @(Get-ChildItem $shotDir -Filter 'Shot*.png' | Where-Object { -not $before.ContainsKey($_.Name) } |
           Sort-Object Name)
if ($shots.Count -ne $expected) { Write-Warning "expected $expected frames, got $($shots.Count)" }
$frameDir = Join-Path ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Output))) (
    [IO.Path]::GetFileNameWithoutExtension($Output) + '_frames')
New-Item -ItemType Directory -Force $frameDir | Out-Null
Get-ChildItem $frameDir -Filter 'f_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
$i = 0
foreach ($s in $shots) { Move-Item -LiteralPath $s.FullName (Join-Path $frameDir ('f_{0:D5}.png' -f $i)); $i++ }
& ffmpeg -v error -y -framerate $Fps -i (Join-Path $frameDir 'f_%05d.png') -c:v libx264 -preset slow -crf $Crf `
    -pix_fmt yuv420p -movflags +faststart $Output
if ($LASTEXITCODE -ne 0) { throw 'ffmpeg failed' }
if (-not $KeepFrames) { Remove-Item -Recurse -Force $frameDir }
[pscustomobject]@{ output = $Output; frames = $shots.Count; expected = $expected; fps = $Fps; keys = $keyLines.Count }
