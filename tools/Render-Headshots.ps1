<#
.SYNOPSIS
  Render the clips of a HEAD SHOT plan (hs_plan.py): every job -> WORK\<id>.mp4 (+ .json). Resumable.
.EXAMPLE
  .\Render-Headshots.ps1 -Plan output\plans\headshot.json -Work output\work\headshot -Only s01B,s05B
  (from pwsh -File, -Only a,b,c arrives as one string: it is split on commas)
.NOTES
  Each job launches the game fresh (seek back after a previous clip is slow). The game owns the screen.
  A failed job is retried once; see docs\HEADSHOT.md.
#>
param(
    [Parameter(Mandatory)][string]$Plan,
    [Parameter(Mandatory)][string]$Work,
    [string[]]$Only,
    [switch]$Force
)
$ErrorActionPreference = 'Continue'
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
if ($Only) { $Only = @($Only | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) }   # "pwsh -File" passes a,b,c as one string
$p = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force $Work | Out-Null
$clip = Join-Path $PSScriptRoot 'Render-Clip.ps1'
$done = 0; $failed = @()
foreach ($j in $p.jobs) {
    if ($Only -and $j.id -notin $Only) { continue }
    $out = Join-Path $Work "$($j.id).mp4"
    if ((Test-Path -LiteralPath $out) -and -not $Force) { "skip $($j.id)"; continue }
    $a = @{ Demo = $j.demo; Start = $j.start; End = $j.end; Output = $out; HudMode = [int]$j.hud; ClearDecals = $true }
    if ($j.camera -eq 'first') { $a.Camera = 'first'; $a.Player = $j.player }
    else { $a.Camera = 'cam'; $a.Cam = $j.cam; $a.Ramp = $j.ramp; $a.Bullet = $j.bullet }
    $ok = $false
    for ($try = 1; $try -le 2 -and -not $ok; $try++) {
        try {
            $r = & $clip @a 2>&1 | Select-Object -Last 1
            "$(Get-Date -Format HH:mm:ss) ok $($j.id) len=$($r.clipLength) wallScale=$($r.wallScale) luma=$($r.meanLuma)"
            $ok = $true
        } catch {
            "$(Get-Date -Format HH:mm:ss) FAILED $($j.id) (try $try): $($_.Exception.Message)"
            try { Stop-UT } catch {}
            Start-Sleep 3
        }
    }
    if ($ok) { $done++ } else { $failed += $j.id }
}
try { Stop-UT } catch {}
"done: $done rendered, failed: $($failed -join ' ')"
