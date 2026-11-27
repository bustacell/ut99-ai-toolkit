<#
.SYNOPSIS
  Rank a player's best moments from *.events.json scans and emit a shot plan.
.DESCRIPTION
  Moments = chains of the player's kills with <= ChainGap seconds between kills, plus flag captures.
  Score = kills^2 + multikill announcer tiers + sprees + 4*capture + density bonus.
  Shots are picked by score until TargetSeconds of footage is reached (MaxPerDemo for variety),
  then ordered as a build-up (best moment last). Top SlowMoCount moments get a slow-motion chase-cam replay.
.EXAMPLE
  .\Find-Highlights.ps1 -Player YourNick -TargetSeconds 90 -PlanOut ..\output\plans\bestof.json -MovieOut ..\output\bestof.mp4
#>
param(
    [string[]]$Scan = (Get-ChildItem (Join-Path (Split-Path $PSScriptRoot) 'output\scans\*.events.json')).FullName,
    [string]$Player = (Get-Content (Join-Path (Split-Path $PSScriptRoot) 'config.json') -Raw | ConvertFrom-Json).player,
    [double]$TargetSeconds = 90,
    [int]$Top = 0,                # optional hard cap on moments
    [int]$MaxPerDemo = 2,
    [int]$SlowMoCount = 3,
    [double]$ChainGap = 3.0,
    [double]$TransitionSeconds = 0.4,
    [string]$Title,
    [string]$PlanOut,
    [string]$MovieOut = (Join-Path (Split-Path $PSScriptRoot) 'output\highlights.mp4')
)
$ErrorActionPreference = 'Stop'
$tierScore = @{ 'Double Kill' = 1; 'Multi Kill' = 2; 'Mega Kill' = 3; 'ULTRA KILL' = 4; 'M O N S T E R K I L L' = 5; 'MONSTER KILL' = 5; 'H O L Y S H I T' = 5 }
$tierRank = @('Double Kill', 'Multi Kill', 'Mega Kill', 'ULTRA KILL', 'MONSTER KILL', 'M O N S T E R K I L L', 'H O L Y S H I T')

function MapName([string]$demo) { (((($demo -replace '\.dem$', '') -replace '_\d\d-\d\d_\d\d-\d\d-\d\d$', '') -replace '^(CTF|DM|DOM|AS)-', '') -replace '[-_\[\]\(\)]+', ' ').Trim() }

$moments = @()
foreach ($file in $Scan) {
    $j = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
    $ev = @($j.events)
    $demo = [IO.Path]::GetFileName($j.demo)
    $kills = @($ev | Where-Object { $_.type -eq 'kill' -and $_.killer -eq $Player -and $_.victim -ne $Player } | Sort-Object t)
    $chains = @(); $cur = @()
    foreach ($k in $kills) {
        if ($cur.Count -and ($k.t - $cur[-1].t) -gt $ChainGap) { $chains += , $cur; $cur = @() }
        $cur += $k
    }
    if ($cur.Count) { $chains += , $cur }
    foreach ($c in $chains) {
        $a = $c[0].t; $b = $c[-1].t; $n = $c.Count
        $multi = @($ev | Where-Object { $_.type -eq 'multikill' -and $_.player -eq $Player -and $_.t -ge $a - 0.1 -and $_.t -le $b + 0.6 })
        $bonus = [double](($multi | ForEach-Object { $tierScore[($_.label -replace '\s+', ' ').Trim()] } | Measure-Object -Sum).Sum)
        $spree = @($ev | Where-Object { $_.type -eq 'spree' -and $_.player -eq $Player -and $_.t -ge $a - 0.1 -and $_.t -le $b + 0.6 }).Count
        $cap = @($ev | Where-Object { $_.type -eq 'flag_captured' -and $_.player -eq $Player -and $_.t -ge $a -and $_.t -le $b + 8 }).Count
        if ($n -lt 2 -and $cap -eq 0) { continue }
        $density = if ($n -ge 2) { ($n - 1) / [math]::Max(0.5, $b - $a) } else { 0 }
        $score = $n * $n + $bonus + $spree + 4 * $cap + 2 * $density
        $topLabel = $multi | ForEach-Object { ($_.label -replace '\s+', ' ').Trim() } | Sort-Object -Property @{ Expression = { [int]$tierScore[[string]$_] } } | Select-Object -Last 1
        $moments += [pscustomobject]@{ demo = $demo; map = (MapName $demo); first = $a; last = $b; kills = $n; score = [math]::Round($score, 2); label = $topLabel; capture = [bool]$cap }
    }
    foreach ($fc in ($ev | Where-Object { $_.type -eq 'flag_captured' -and $_.player -eq $Player })) {
        if (-not ($moments | Where-Object { $_.demo -eq $demo -and $fc.t -ge $_.first -and $fc.t -le $_.last + 8 })) {
            $moments += [pscustomobject]@{ demo = $demo; map = (MapName $demo); first = $fc.t - 6; last = $fc.t; kills = 0; score = 4; label = 'Flag Capture'; capture = $true }
        }
    }
}

function ShotLen($m) { ($m.last + 1.5) - [math]::Max(0, $m.first - 2.5) }
$slowLen = (1.0 + 0.5) / 0.35

$picked = @(); $perDemo = @{}; $total = 0.0
foreach ($m in ($moments | Sort-Object score -Descending)) {
    if ($Top -gt 0 -and $picked.Count -ge $Top) { break }
    if ($perDemo[$m.demo] -ge $MaxPerDemo) { continue }
    $len = ShotLen $m
    if ($len -gt 14) { continue }                       # keep shots punchy
    $extra = if ($picked.Count -lt $SlowMoCount -and $m.kills -ge 3) { $slowLen } else { 0 }
    if ($total + $len + $extra -gt $TargetSeconds + 3) { continue }
    $m | Add-Member -NotePropertyName slowmo -NotePropertyValue ([bool]$extra) -Force
    $picked += $m; $perDemo[$m.demo] = 1 + [int]$perDemo[$m.demo]
    $total += $len + $extra - $TransitionSeconds
    if ($total -ge $TargetSeconds - 3) { break }
}
# build-up: weaker moments first, best last
$picked = $picked | Sort-Object score

$shots = @()
foreach ($m in $picked) {
    $cap = if ($m.label) { ($m.label.ToUpper().Trim() -replace 'M O N S T E R\s*K I L L', 'MONSTER KILL' -replace 'H O L Y\s*S H I T', 'HOLY SHIT') } elseif ($m.kills -ge 2) { "$($m.kills) KILLS" } else { 'FLAG CAPTURE' }
    $shots += [ordered]@{ demo = $m.demo; startSeconds = [math]::Round([math]::Max(0, $m.first - 2.5), 2); endSeconds = [math]::Round($m.last + 1.5, 2); camera = 'first_person'; player = $Player; speed = 1.0; hud = $true; caption = $cap; subcaption = $m.map; chip = $(if ($m.kills -ge 2) { "$($m.kills) KILLS" } else { '' }); note = "score $($m.score), $($m.kills) kills" }
    if ($m.slowmo) {
        $shots += [ordered]@{ demo = $m.demo; startSeconds = [math]::Round($m.last - 1.0, 2); endSeconds = [math]::Round($m.last + 0.5, 2); camera = 'third_person'; player = $Player; speed = 0.35; hud = $false; note = 'slow-motion finisher' }
    }
}
$plan = [ordered]@{ output = $MovieOut; resolution = '1920x1080'; fps = 60; transition = 'fade'; transitionSeconds = $TransitionSeconds; title = $Title; outro = $Player; shots = $shots }
if ($PlanOut) {
    New-Item -ItemType Directory -Force (Split-Path $PlanOut) | Out-Null
    $plan | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $PlanOut -Encoding UTF8
}
$picked | Format-Table demo, first, last, kills, score, label, slowmo -AutoSize | Out-Host
"moments: $($moments.Count) candidates, $($picked.Count) picked, ~$([math]::Round($total)) s of footage" | Out-Host
