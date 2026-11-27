# Scripted UnrealEd tour for making-of footage, recorded by ffmpeg (desktop, visible cursor).
# Before: start UnrealEd.exe from System, load the map via the editor's Command bar ("MAP LOAD FILE=..\Maps\X.unr";
# a map name on the command line is ignored), keep the default 4-view layout, window maximized. Coordinates below
# are for 1920x1080. Afterwards close UnrealEd WITHOUT saving (kill the process) and compare the map's hash.
param([string]$Out = "$env:TEMP\dd-tour\ued-raw.mkv")
. "$PSScriptRoot\UedInput.ps1"
Focus-Ued
Move-To 1500 700
$ff = Start-Process ffmpeg -ArgumentList '-loglevel', 'error', '-y', '-f', 'gdigrab', '-framerate', '30', '-draw_mouse', '1',
    '-i', 'desktop', '-t', '34', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', $Out -PassThru -WindowStyle Hidden
Start-Sleep 3                                          # hold: the 4-view layout
# perspective viewport (x 120..1285, y 562..995): right-drag looks around, left-drag moves forward/turns
Drag-Rel 700 780 350 0 'right' 3000             # look around (raw relative motion, see UedInput.ps1)
Drag-Rel 700 780 -220 -110 'right' 2500          # turn back and look up to the dome and the Spark
Drag-Rel 700 780 0 -160 'left' 2000              # move forward
Start-Sleep 1
# top viewport (x 120..1285, y 98..532): a click gives it focus, then zoom into the atrium and back out
Click-At 1150 130
Wheel 790 365 4
Start-Sleep -Milliseconds 1200
Wheel 790 365 -4
Start-Sleep 1
# the command line: a real lighting rebuild (in memory only, never saved)
Click-At 380 1016
Press-Keys '^a'
foreach ($ch in 'LIGHT APPLY'.ToCharArray()) { Press-Keys ([string]$ch -replace ' ', ' '); Start-Sleep -Milliseconds 60 }
Start-Sleep -Milliseconds 400
Press-Keys '{ENTER}'
Move-To 1500 700
$ff.WaitForExit(60000) | Out-Null
"recorded $Out"
