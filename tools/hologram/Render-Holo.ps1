# Renders every hologram shot of the showcase in 4K with two Blender workers side by side (more froze a 16 GB PC).
# Resumable: frames that exist are skipped. Log: logs\hologram-render-<worker>.log
# Disk: each 4K PNG is ~6.6 MB, 10 maps are ~75 GB. If the disk fills up, Blender writes empty and truncated PNGs:
# verify every frame (docs/HOLOGRAM.md) before assembling.
#   .\Render-Holo.ps1 [-Keys pd,washme] [-Workers 2]
param([string[]]$Keys, [int]$Workers = 2)
. "$PSScriptRoot\..\DDConfig.ps1"
$B = Resolve-DDPath $(if ($DDCfg.blender) { $DDCfg.blender } else { '..\blender\blender.exe' })
$S = Join-Path $PSScriptRoot 'gtm_holo.py'
$W = if ($env:UTDD_HOLO_WORK) { $env:UTDD_HOLO_WORK } else { Join-Path $DDOut 'work\hologram' }
$logs = Join-Path $DDRoot 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$lineup = Get-Content -LiteralPath (Join-Path $W 'lineup.json') -Raw | ConvertFrom-Json
$jobs = foreach ($e in $lineup) {
    if ($Keys -and ($Keys -notcontains $e.key)) { continue }
    foreach ($shot in 'build', 'combo') { [pscustomobject]@{ key = $e.key; shot = $shot } }
}
$procs = for ($wk = 0; $wk -lt $Workers; $wk++) {      # not $w: PowerShell names ignore case, $w would be $W
    $mine = for ($i = $wk; $i -lt $jobs.Count; $i += $Workers) { $jobs[$i] }
    $lines = foreach ($j in $mine) {
        "& '$B' -b -P '$S' -- '$W\$($j.key)\config.json' $($j.shot) '$W\$($j.key)\r4k\$($j.shot)' --res 3840 2160 2>&1 | Select-String 'FRAME \d+0 |Error|Traceback|END_VIEW'"
    }
    $script = "$W\render-worker$wk.ps1"
    Set-Content -LiteralPath $script -Value $lines
    Start-Process pwsh -ArgumentList '-NoProfile', '-File', $script -RedirectStandardOutput "$logs\hologram-render-$wk.log" -WindowStyle Hidden -PassThru
}
$procs | Wait-Process
"done"
