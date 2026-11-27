# Records the short real-footage flash of every map: my first-person view from just before the shot to just after
# the combo, cinematic HUD. UT owns the screen while this runs. Check every flash's HUD text afterwards (other players'
# names and chat end up in the film; blur them with "hide" in lineup.json, see docs/HOLOGRAM.md).
#   .\Record-Flashes.ps1 [-Keys pd,washme] [-Force]
param([string[]]$Keys, [switch]$Force)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\DDConfig.ps1"
$inv = [Globalization.CultureInfo]::InvariantCulture
$W = if ($env:UTDD_HOLO_WORK) { $env:UTDD_HOLO_WORK } else { Join-Path $DDOut 'work\hologram' }
$env:DD_SEEK_TIMEOUT = '600'
$lineup = Get-Content -LiteralPath (Join-Path $W 'lineup.json') -Raw | ConvertFrom-Json
foreach ($e in $lineup) {
    if ($Keys -and ($Keys -notcontains $e.key)) { continue }
    $cfg = Get-Content -LiteralPath "$W\$($e.key)\config.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    $out = "$W\$($e.key)\flash.mp4"
    if ((Test-Path -LiteralPath $out) -and -not $Force) { "$($e.key): exists"; continue }
    try { $path = Resolve-DDDemo $e.demo } catch { "$($e.key): DEMO NOT FOUND $($e.demo)"; continue }
    $start = ([double]$cfg.t_fire - 1.6).ToString('0.###', $inv)
    $end = ([double]$cfg.t_combo + 1.2).ToString('0.###', $inv)
    "$($e.key): $path $start..$end"
    try {
        & (Join-Path $PSScriptRoot '..\Render-Clip.ps1') -Demo $path -Start $start -End $end -Player $DDPlayer -Camera first -HudMode 1 -Output $out
    } catch { "$($e.key): FAILED $_" }
}
