<#
.SYNOPSIS
  Render all shots of a cinematic movie plan (tools\plan_movie.py) and assemble the movie.
.EXAMPLE
  .\Render-Movie.ps1 -Plan ..\output\plans\cine.json
.NOTES
  Shots are rendered grouped by demo (ascending start). The running game is reused only for
  forward jumps (uDemo rewinds are slow). A failed run can simply be restarted: a finished shot is
  reused only if its report says valid AND its inputs (demo, times, speed, camera, HUD, ...) still match the
  plan (<id>.inputs.txt). A changed or invalid shot is moved aside (<id>.stale.* / <id>.invalid.*, never
  deleted) and rendered again. A shot that fails twice is left out; assembly then stops with the list of
  missing shots. -Preview assembles anyway with a dark slate of the same length in each gap (the music stays
  in sync) into a separate *_PREVIEW file (assemble_movie.py; other assemblers get no extra argument).
#>
param([Parameter(Mandatory)][string]$Plan, [switch]$AssembleOnly, [string[]]$Only, [string]$Assembler = 'assemble_movie.py',
      [switch]$NoAssemble, [switch]$Preview)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
function F([double]$x) { $x.ToString('0.###', $inv) }
$p = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
$work = Join-Path $DDOut ('work\' + [IO.Path]::GetFileNameWithoutExtension($p.output))
New-Item -ItemType Directory -Force $work | Out-Null
$log = Join-Path $work 'render.log'
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force

# Everything that changes the picture of a shot (Output / KeepGameOpen / Reuse don't).
function Get-ShotKey([hashtable]$a) {
    ($a.Keys | Where-Object { $_ -notin 'Output', 'KeepGameOpen', 'Reuse' } | Sort-Object |
        ForEach-Object { "$_=$(@($a[$_]) -join ',')" }) -join "`n"
}
# Move a clip and its report aside (footage is never deleted): <id>.<tag>.mp4 / .json
function Move-ShotAside([string]$out, [string]$tag) {
    foreach ($ext in '.mp4', '.json') {
        $f = [IO.Path]::ChangeExtension($out, $ext)
        if (Test-Path -LiteralPath $f) { Move-Item -LiteralPath $f ([IO.Path]::ChangeExtension($out, ".$tag$ext")) -Force }
    }
}
# $null = reusable; otherwise the reason it is not
function Test-ShotReusable([string]$out, [string]$keyFile, [string]$key) {
    $rep = [IO.Path]::ChangeExtension($out, '.json')
    if (-not (Test-Path -LiteralPath $rep)) { return 'no report' }
    try { $r = Get-Content -LiteralPath $rep -Raw | ConvertFrom-Json } catch { return 'unreadable report' }
    if (-not $r.valid) { return 'report says invalid' }
    if (Test-Path -LiteralPath $keyFile) {
        if ((Get-Content -LiteralPath $keyFile -Raw).Trim() -ne $key.Trim()) { return 'shot changed in the plan' }
    } else {
        Set-Content -LiteralPath $keyFile $key -Encoding UTF8    # rendered before input tracking existed: adopt once
    }
    return $null
}
# Render-Clip arguments of a plan shot: one place, used for rendering and for the pre-assembly check
function New-ShotArgs($s, [string]$out) {
    $a = @{ Demo = $s.demo; Start = (F $s.start); End = (F $s.end); Speed = [double]$s.speed; Output = $out
            KeepGameOpen = $true; NoGore = (-not $s.gore); HudMode = [int]$s.hud }
    if ($s.ramp) { $a.Ramp = $s.ramp }
    if ($s.type) { $a.Type = $s.type }
    if ($s.kind -eq 'first') { $a.Camera = 'first'; $a.Player = $s.player }
    else { $a.Camera = 'cam'; $a.Cam = $s.cam; if ($s.tags) { $a.Tags = @($s.tags) } }
    $a
}
# Before ANY assembly (also -AssembleOnly, and after -Only rendered just a few shots): every UT shot of the plan
# must have a valid clip rendered from its current inputs. Anything else is moved aside, so the assembler sees a
# gap (and refuses, or fills a slate with -Preview) instead of cutting stale footage into the movie.
function Invoke-AssemblyGate($Shots, [string]$Work) {
    $moved = 0
    foreach ($s in $Shots) {
        $out = Join-Path $Work "$($s.id).mp4"
        if (-not (Test-Path -LiteralPath $out)) { continue }
        $why = Test-ShotReusable $out (Join-Path $Work "$($s.id).inputs.txt") (Get-ShotKey (New-ShotArgs $s $out))
        if ($why) {
            $tag = if ($why -eq 'report says invalid') { 'invalid' } else { 'stale' }
            Move-ShotAside $out $tag; $moved++
            $msg = "not assembling $($s.id): $why (clip kept as $($s.id).$tag.mp4; re-render with -Only $($s.id))"
            Write-Host $msg; if ($log) { Add-Content $log $msg }
        }
    }
    $moved
}

if (-not $AssembleOnly) {
    # only shots rendered in UT (plans may also hold card / grid / endcard items for the assembler)
    $shots = @($p.shots) | Where-Object { $_.kind -in 'first', 'cam' -and (-not $Only -or $_.id -in $Only) } | Sort-Object demo, { [double]$_.start }
    $prevDemo = $null; $prevEnd = -1e9; $n = 0
    foreach ($s in $shots) {
        $n++
        $out = Join-Path $work "$($s.id).mp4"
        $a = New-ShotArgs $s $out
        $key = Get-ShotKey $a                     # from the plan, before a fallback below changes $a
        $keyFile = Join-Path $work "$($s.id).inputs.txt"
        if (Test-Path -LiteralPath $out) {
            $why = Test-ShotReusable $out $keyFile $key
            if (-not $why) { Add-Content $log "[$n/$($shots.Count)] reuse $($s.id)"; continue }
            $msg = "[$n/$($shots.Count)] re-render $($s.id): $why (old clip kept as $($s.id).stale.mp4)"
            Write-Host $msg; Add-Content $log $msg
            Move-ShotAside $out 'stale'
        }
        if (Test-Path -LiteralPath $keyFile) { Remove-Item -LiteralPath $keyFile }
        if ($prevDemo -eq $s.demo -and [double]$s.start -ge $prevEnd + 3 -and (Get-UTProcess)) { $a.Reuse = $true }
        $msg = "[{0}/{1}] {2} {3} {4}-{5} {6} x{7} {8}" -f $n, $shots.Count, $s.id, $s.demo, $s.start, $s.end, $s.kind, $s.speed, $s.moment.type
        Write-Host $msg; Add-Content $log $msg
        $ok = $false
        for ($try = 1; $try -le 2 -and -not $ok; $try++) {
            try { [void](& (Join-Path $PSScriptRoot 'Render-Clip.ps1') @a); $ok = $true }
            catch {
                Add-Content $log "   try $try failed: $($_.Exception.Message)"
                Stop-UT -Force                  # only the UT this toolkit started; a user's own UT is never killed
                Start-Sleep 2
                $a.Remove('Reuse')
                # fallback for first-person of a player that is not viewable: chase cam
                if ($try -eq 1 -and $s.kind -eq 'first' -and $_.Exception.Message -match 'Camera is on|did not engage|not found') {
                    $a.Camera = 'cam'; $a.Remove('Player')
                    $a.Cam = "mode=chase tgtname=$([uri]::EscapeDataString($s.player)) dist=230 h=75 lag=0.88 off=20"
                }
            }
        }
        if ($ok) { Set-Content -LiteralPath $keyFile $key -Encoding UTF8 }
        else {
            Add-Content $log "   SKIPPED $($s.id)"
            Move-ShotAside $out 'invalid'         # a failed validation leaves a clip behind: never assemble it
        }
        $prevDemo = $s.demo; $prevEnd = [double]$s.end
    }
    Stop-UT
}
if (-not $NoAssemble) {
    [void](Invoke-AssemblyGate (@($p.shots) | Where-Object { $_.kind -in 'first', 'cam' }) $work)
    $extra = @(); if ($Preview) { $extra = @('--preview') }
    python (Join-Path $PSScriptRoot $Assembler) $Plan $work @extra
    if ($LASTEXITCODE -ne 0) { throw 'assembly failed (see the missing/invalid shots above; -Preview assembles with gaps)' }
}
