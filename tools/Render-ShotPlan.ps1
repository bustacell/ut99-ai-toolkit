<#
.SYNOPSIS
  Render every shot of a shot plan (JSON) and assemble them into one MP4.
.DESCRIPTION
  Shot plan format:
  { "output": "...mp4", "transition": "fade"|"none", "transitionSeconds": 0.4,
    "title": "optional title card text", "outro": "optional outro text",
    "shots": [ { "demo": "X.dem", "startSeconds": 155, "endSeconds": 170,
                 "camera": "first_person"|"third_person"|"free"|"recorder",
                 "player": "YourNick", "speed": 1.0, "hud": true,
                 "caption": "ULTRA KILL", "subcaption": "CTF-Bolt_HE" } ] }
  Times are demo seconds (uDemo SeekTo time). Shots are rendered grouped by demo (one game launch
  per demo) and assembled in plan order. Already rendered shots in the work folder are reused (-Resume).
#>
param([Parameter(Mandatory)][string]$Plan, [switch]$KeepClips, [switch]$Resume)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
function F([double]$x) { $x.ToString('0.###', $inv) }
. (Join-Path $PSScriptRoot 'DDConfig.ps1')   # portable binDirs on PATH
$p = Get-Content $Plan -Raw | ConvertFrom-Json
$ffmpeg = (Get-Command ffmpeg).Source
$ffprobe = Join-Path (Split-Path $ffmpeg) 'ffprobe.exe'
$work = Join-Path (Split-Path $PSScriptRoot) ('output\work\' + [IO.Path]::GetFileNameWithoutExtension($p.output))
New-Item -ItemType Directory -Force $work | Out-Null
$camMap = @{ first_person = 'first'; third_person = 'behind'; free = 'free'; recorder = 'recorder'; first = 'first'; behind = 'behind' }
$shots = @($p.shots)
$n = $shots.Count
$font = 'C\:/Windows/Fonts/arialbd.ttf'
$fontR = 'C\:/Windows/Fonts/arial.ttf'

# --- render (grouped by demo) ---------------------------------------------------------
$order = 0..($n - 1) | Sort-Object { $shots[$_].demo }, { [double]$shots[$_].startSeconds }
$prevDemo = $null; $done = 0; $renderedAny = $false
foreach ($idx in $order) {
    $s = $shots[$idx]; $done++
    $out = Join-Path $work ('shot{0:d2}.mp4' -f ($idx + 1))
    if ($Resume -and (Test-Path $out)) { Write-Host "[$done/$n] reuse $out"; continue }
    $args = @{
        Demo = $s.demo; Start = (F $s.startSeconds); End = (F $s.endSeconds)
        Camera = $camMap[[string]$s.camera]; Speed = [double]$(if ($s.speed) { $s.speed } else { 1 }); Output = $out; KeepGameOpen = $true
    }
    if ($s.player) { $args.Player = $s.player }
    if ($s.PSObject.Properties['hud'] -and -not $s.hud) { $args.HideHud = $true }
    # reuse the running game only for forward jumps (uDemo rewinds are very slow on long demos)
    if ($prevDemo -eq $s.demo -and [double]$s.startSeconds -ge $prevEnd + 3) { $args.Reuse = $true }
    Write-Host ("[{0}/{1}] shot{2:d2} {3} {4}-{5}s {6} x{7}" -f $done, $n, ($idx + 1), $s.demo, $s.startSeconds, $s.endSeconds, $s.camera, $args.Speed)
    $tries = 0
    while ($true) {
        try { [void](& (Join-Path $PSScriptRoot 'Render-Clip.ps1') @args); break }
        catch {
            $tries++
            Write-Warning "shot$($idx + 1) failed: $($_.Exception.Message)"
            Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
            Stop-UT -Force                  # only the UT this toolkit started; a user's own UT is never killed
            Start-Sleep 2
            $args.Remove('Reuse')
            if ($tries -ge 2) { throw }
        }
    }
    $prevDemo = $s.demo; $prevEnd = [double]$s.endSeconds; $renderedAny = $true
}
if ($renderedAny) { Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force; Stop-UT }

# --- captions, title, outro (graphics from make_graphics.py) ------------------------------
$py = Join-Path $PSScriptRoot 'make_graphics.py'
$enc = @('-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '60', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2')
Push-Location $work
try {
    $pieces = @()
    $bestShot = 'shot{0:d2}.mp4' -f $n          # plans are ordered as a build-up: last shot = best
    if ($p.title) {
        python $py title title.png --name $p.title --top 'UNREAL TOURNAMENT' --bottom 'COMBOGIB  BEST OF'
        if ($LASTEXITCODE -ne 0) { throw 'title graphic failed' }
        $fc = "[0:v]gblur=sigma=18,eq=brightness=-0.04:saturation=0.8,fade=t=in:st=0:d=0.6[b];" +
              "[1:v]format=rgba,fade=t=in:st=0.35:d=0.6:alpha=1,fade=t=out:st=3.1:d=0.5:alpha=1[g];" +
              "[b][g]overlay=x=0:y='max(0,24*(1-(t-0.35)/0.7))'[v];[0:a]volume=0.35,afade=t=in:d=0.8,afade=t=out:st=3.1:d=0.5[a]"
        & $ffmpeg -hide_banner -loglevel error -y -t 3.6 -i $bestShot -loop 1 -framerate 60 -t 3.6 -i title.png -filter_complex $fc -map '[v]' -map '[a]' @enc title.mp4
        if ($LASTEXITCODE -ne 0) { throw 'title encode failed' }
        $pieces += 'title.mp4'
    }
    for ($i = 0; $i -lt $n; $i++) {
        $src = 'shot{0:d2}.mp4' -f ($i + 1)
        $s = $shots[$i]
        if ($s.caption) {
            $png = 'lt{0:d2}.png' -f ($i + 1)
            $gargs = @('lowerthird', $png, '--title', [string]$s.caption, '--sub', [string]$s.subcaption)
            if ($s.chip) { $gargs += '--chip', [string]$s.chip }
            python $py @gargs
            if ($LASTEXITCODE -ne 0) { throw "lower third failed for $src" }
            $fc = "[1:v]format=rgba,fade=t=in:st=0.35:d=0.3:alpha=1,fade=t=out:st=3.2:d=0.45:alpha=1[g];" +
                  "[0:v][g]overlay=x='if(lt(t,0.35),-280,if(lt(t,0.8),-280+280*(1-pow(1-(t-0.35)/0.45,3)),0))':y=0:shortest=1[v]"
            $dst = 'cap_' + $src
            & $ffmpeg -hide_banner -loglevel error -y -i $src -loop 1 -framerate 60 -i $png -filter_complex $fc -map '[v]' -map '0:a' @enc $dst
            if ($LASTEXITCODE -ne 0) { throw "caption encode failed for $src" }
            $pieces += $dst
        } else { $pieces += $src }
    }
    if ($p.outro) {
        python $py outro outro.png --name ([string]$p.outro).ToUpper() --bottom 'UNREAL TOURNAMENT  COMBOGIB'
        if ($LASTEXITCODE -ne 0) { throw 'outro graphic failed' }
        $fc = "[0:v]gblur=sigma=18,eq=brightness=-0.06:saturation=0.8[b];" +
              "[1:v]format=rgba,fade=t=in:st=0.3:d=0.6:alpha=1[g];" +
              "[b][g]overlay=0:0,fade=t=out:st=2.6:d=0.8[v];[0:a]volume=0.35,afade=t=out:st=2.2:d=1.2[a]"
        & $ffmpeg -hide_banner -loglevel error -y -sseof -3.4 -i $bestShot -loop 1 -framerate 60 -t 3.4 -i outro.png -filter_complex $fc -map '[v]' -map '[a]' -t 3.4 @enc outro.mp4
        if ($LASTEXITCODE -ne 0) { throw 'outro encode failed' }
        $pieces += 'outro.mp4'
    }

    # --- assemble ------------------------------------------------------------------------
    $T = if ($p.transitionSeconds) { [double]$p.transitionSeconds } else { 0.4 }
    $durs = $pieces | ForEach-Object { [double]::Parse((& $ffprobe -v error -show_entries format=duration -of csv=p=0 $_), $inv) }
    $inputs = @(); foreach ($c in $pieces) { $inputs += '-i', $c }
    $g = ''
    for ($k = 0; $k -lt $pieces.Count; $k++) {
        $g += "[$($k):v]settb=AVTB,fps=60,format=yuv420p,setsar=1[v$($k)n];[$($k):a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a$($k)n];"
    }
    $lastV = '[v0n]'; $lastA = '[a0n]'; $acc = $durs[0]
    for ($k = 1; $k -lt $pieces.Count; $k++) {
        if ($p.transition -eq 'none') { $t2 = 0.04 } else { $t2 = $T }
        $g += "$lastV[v$($k)n]xfade=transition=fade:duration=$(F $t2):offset=$(F ($acc - $t2))[vx$k];"
        $g += "$lastA[a$($k)n]acrossfade=d=$(F $t2)[ax$k];"
        $lastV = "[vx$k]"; $lastA = "[ax$k]"
        $acc = $acc + $durs[$k] - $t2
    }
    $g = $g.TrimEnd(';')
    Set-Content 'filter.txt' $g -Encoding Ascii
    $outFull = [IO.Path]::GetFullPath($p.output)
    & $ffmpeg -hide_banner -loglevel error -y @inputs -/filter_complex filter.txt -map $lastV -map $lastA -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 60 -c:a aac -b:a 192k -movflags +faststart $outFull
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg montage failed ($LASTEXITCODE)" }
} finally { Pop-Location }

$probe = & $ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,avg_frame_rate -of json $p.output | ConvertFrom-Json
if (-not $KeepClips) { Remove-Item $work -Recurse -Force }
[pscustomobject]@{ output = $p.output; shots = $n; duration = [double]::Parse($probe.format.duration, $inv); video = ($probe.streams | Where-Object codec_type -eq 'video' | ForEach-Object { "$($_.width)x$($_.height)@$($_.avg_frame_rate)" }) }
