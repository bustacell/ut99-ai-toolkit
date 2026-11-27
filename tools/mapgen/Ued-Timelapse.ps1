# Editor timelapse: UnrealEd imports cumulative T3D stages (t3d_stages.py) one after another, rebuilds and lights
# each, and a screenshot is taken per stage. Assemble with ffmpeg (blend between stages for smoothness).
# Before: UnrealEd open and maximized with the real map loaded (its MyLevel textures stay in memory for the
# imports), views framed. Never save; kill UnrealEd afterwards.
param([Parameter(Mandatory)][string]$StageDir, [Parameter(Mandatory)][string]$OutDir)
. "$PSScriptRoot\UedInput.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$stages = Get-ChildItem $StageDir -Filter 'stage_*.t3d' | Sort-Object Name
function Send-Command([string]$cmd) {
    Focus-Ued; Click-At 380 1016; Press-Keys '^a'; Press-Keys $cmd; Press-Keys '{ENTER}'
}
$k = 0
foreach ($s in $stages) {
    $k++
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Send-Command "MAP IMPORT FILE=$($s.FullName)"; Start-Sleep -Milliseconds ([int](3500 + 250 * $k))
    Send-Command 'MAP REBUILD';                     Start-Sleep -Milliseconds ([int](3000 + 250 * $k))
    Send-Command 'LIGHT APPLY';                     Start-Sleep -Milliseconds ([int](4000 + 300 * $k))
    Move-To 1900 1070                                # cursor out of the picture
    Start-Sleep -Milliseconds 500
    Save-Screen (Join-Path $OutDir ("s{0:D2}.png" -f $k))
    "{0} {1:N0} s" -f $s.Name, $sw.Elapsed.TotalSeconds
}
