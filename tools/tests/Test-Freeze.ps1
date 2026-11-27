# Freeze test (docs\BULLETTIME.md): how does 0.02x look on your machine and demos? Renders a few short clips of ONE
# combo to output\work\freeze_test; check them with:  python tests\freeze_motion.py <clip.mp4>
#   .\tests\Test-Freeze.ps1 -Demo <demo file name> -T <combo time> -Combo "x,y,z"
# (combo time and location: output\rare.json, "t" and "where.combo")
param([Parameter(Mandatory)][string]$Demo, [Parameter(Mandatory)][double]$T, [Parameter(Mandatory)][string]$Combo)
$ErrorActionPreference = 'Continue'
. (Join-Path (Split-Path $PSScriptRoot) 'DDConfig.ps1')
$env:DD_SEEK_TIMEOUT = '600'
$rc = Join-Path (Split-Path $PSScriptRoot) 'Render-Clip.ps1'
$out = Join-Path $DDOut 'work\freeze_test'
New-Item -ItemType Directory -Force $out | Out-Null
$inv = [Globalization.CultureInfo]::InvariantCulture
function F([double]$x) { $x.ToString('0.###', $inv) }
$shots = @(
    @{ id = 'orbit_x0.02';  s = $T - 0.12; e = $T + 0.08; speed = 0.02;  cam = "mode=orbit p=$Combo r=380 h=60 a0=200 w=38 lag=0.5 off=0 rt=1" },
    @{ id = 'orbit_x0.005'; s = $T - 0.02; e = $T + 0.04; speed = 0.005; cam = "mode=orbit p=$Combo r=380 h=60 a0=200 w=38 lag=0.5 off=0 rt=1" },
    @{ id = 'ramp_orbit';   s = $T - 1.0;  e = $T + 0.06; ramp = "$(F ($T - 1.0)):1,$(F ($T - 0.3)):1,$(F $T):0.02"
       cam = "mode=orbit p=$Combo r=420 h=80 a0=90 w=30 lag=0.5 off=0 rt=1" }
)
foreach ($s in $shots) {
    $o = Join-Path $out "$($s.id).mp4"
    if (Test-Path -LiteralPath $o) { "skip $($s.id)"; continue }
    $a = @{ Demo = $Demo; Start = (F $s.s); End = (F $s.e); Camera = 'cam'; Cam = $s.cam; HudMode = 2; Output = $o }
    if ($s.ramp) { $a.Ramp = $s.ramp } else { $a.Speed = $s.speed }
    "$(Get-Date -f HH:mm:ss) start $($s.id)"
    try { & $rc @a | Out-Null; "$(Get-Date -f HH:mm:ss) done  $($s.id)" } catch { "$(Get-Date -f HH:mm:ss) FAIL  $($s.id): $_" }
}
"ALLDONE"
