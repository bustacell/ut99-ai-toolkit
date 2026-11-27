<#
.SYNOPSIS
  Read-only preflight: checks the install before a long scan or render, and optionally a movie plan.
  It launches nothing and changes nothing (a temporary file proves each work folder is writable and is removed).
.EXAMPLE
  .\Test-Toolkit.ps1
  .\Test-Toolkit.ps1 -Plan ..\output\plans\gravity.json
.NOTES
  Each line is OK, WARN (works, but look at it) or FAIL (fix first). Exit code 1 if anything failed.
#>
param([string]$Plan)
$ErrorActionPreference = 'Stop'
$script:fails = 0; $script:warns = 0
function Say([string]$Level, [string]$What, [string]$Detail = '') {
    $c = @{ OK = 'Green'; WARN = 'Yellow'; FAIL = 'Red' }[$Level]
    Write-Host ('{0,-4} ' -f $Level) -ForegroundColor $c -NoNewline
    Write-Host $What -NoNewline
    if ($Detail) { Write-Host "  ($Detail)" -ForegroundColor DarkGray } else { Write-Host }
    if ($Level -eq 'FAIL') { $script:fails++ } elseif ($Level -eq 'WARN') { $script:warns++ }
}
function Test-Writable([string]$Dir) {
    try {
        New-Item -ItemType Directory -Force $Dir | Out-Null
        $f = Join-Path $Dir (".preflight-" + [guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllText($f, 'x'); [IO.File]::Delete($f); $true
    } catch { $false }
}

# --- config ---------------------------------------------------------------------------------------------
$root = Split-Path -Parent $PSScriptRoot
$cfgFile = Join-Path $root 'config.json'
if (-not (Test-Path -LiteralPath $cfgFile)) { Say FAIL 'config.json' 'missing: run setup\Setup.ps1 first'; exit 1 }
try { . (Join-Path $PSScriptRoot 'DDConfig.ps1') } catch { Say FAIL 'config.json' $_.Exception.Message; exit 1 }
if (-not $DDPlayer -or $DDPlayer -eq 'YourNick') { Say WARN 'player' 'config "player" is not set to your in-game name' }
else { Say OK 'config.json' 'player set' }

# --- game --------------------------------------------------------------------------------------------
$sys = Join-Path $DDUT 'System'
if (-not (Test-Path -LiteralPath (Join-Path $sys 'UnrealTournament.exe'))) { Say FAIL 'Unreal Tournament' "not found in $DDUT" }
else {
    Say OK 'Unreal Tournament' $DDUT
    foreach ($pkg in 'udemo.u', 'DemoDirector.u') {
        if (Test-Path -LiteralPath (Join-Path $sys $pkg)) { Say OK $pkg } else { Say FAIL $pkg 'missing in UT\System: run setup again' }
    }
    $userIni = Join-Path $sys 'User.ini'
    $want = "exec $(Join-Path $DDRuntime 'cmd.txt')"
    $bind = if (Test-Path -LiteralPath $userIni) { Select-String -LiteralPath $userIni -Pattern '^ScrollLock=' | Select-Object -First 1 }
    if ($bind -and $bind.Line -eq "ScrollLock=$want") { Say OK 'command key binding' }
    else { Say WARN 'command key binding' 'ScrollLock is not bound to this toolkit; it is fixed automatically on the next start' }
}

# --- demos ------------------------------------------------------------------------------------------
$dirs = Get-DDDemoDirs
$gone = @($dirs | Where-Object { -not (Test-Path -LiteralPath $_) })
foreach ($d in $gone) { Say WARN 'demo folder unreachable' "$d (external drive unplugged?)" }
$ix = Get-DDDemoIndex
$n = ($ix.Values | ForEach-Object { $_.Count } | Measure-Object -Sum).Sum
if ($n) { Say OK 'demos' "$n files in $($dirs.Count - $gone.Count) reachable folder(s)" } else { Say WARN 'demos' 'no .dem files found in the demo folders' }
$amb = @($ix.Keys | Where-Object { Test-DDDemoAmbiguous $ix[$_] })
if ($amb) {
    # handled: these get IDs with a size suffix; old scans stored under the bare name are not used for them
    $old = @($amb | Where-Object { Test-Path -LiteralPath (Join-Path $DDOut "scans\$([IO.Path]::GetFileNameWithoutExtension($_)).events.json") })
    Say OK 'shared demo names' "$($amb.Count) name(s) are different recordings in several folders; they get IDs <name>~<size>"
    if ($old) { Say WARN 'scans under a shared name' "$($old.Count) old scan(s) stored under the bare name belong to only one recording: rename to the ID (docs) or rescan" }
}

# --- tools ------------------------------------------------------------------------------------------
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    Say FAIL 'FFmpeg' 'ffmpeg/ffprobe not on PATH (nor in config binDirs)'
} elseif (-not (& ffmpeg -hide_banner -formats 2>$null | Select-String libopenmpt)) { Say FAIL 'FFmpeg' 'built without libopenmpt (UT music)' }
else { Say OK 'FFmpeg' 'with libopenmpt' }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Say FAIL 'Python' 'not on PATH' }
else {
    & python -c "import numpy, PIL" 2>$null
    if ($LASTEXITCODE) { Say FAIL 'Python packages' 'numpy and Pillow needed: python -m pip install numpy pillow' } else { Say OK 'Python' 'numpy + Pillow' }
}
if ($DDCfg.obsDir -and (Test-Path -LiteralPath (Join-Path $DDCfg.obsDir 'obs64.exe'))) { Say OK 'OBS Studio' $DDCfg.obsDir }
else { Say WARN 'OBS Studio' 'not found (needed for recording, not for scans)' }
if (Test-Path -LiteralPath (Join-Path $DDRuntime 'obs-websocket.json')) { Say OK 'OBS WebSocket settings' 'present (not shown)' }
else { Say WARN 'OBS WebSocket settings' 'runtime\obs-websocket.json missing: run setup again before recording' }
if ($DDCfg.blender) {
    if (Test-Path -LiteralPath (Resolve-DDPath $DDCfg.blender)) { Say OK 'Blender' } else { Say WARN 'Blender' "config path not found: $($DDCfg.blender)" }
}

# --- folders, privacy, running jobs -------------------------------------------------------------------
foreach ($d in 'output', 'runtime', 'logs') {
    if (Test-Writable (Join-Path $root $d)) { Say OK "$d\ writable" } else { Say FAIL "$d\ not writable" (Join-Path $root $d) }
}
if (Test-Path -LiteralPath (Join-Path $root '.git')) {
    $hp = (& git -C $root config core.hooksPath 2>$null)
    if ($hp -eq '.githooks') { Say OK 'privacy hook' 'enabled' }
    else { Say WARN 'privacy hook' 'not enabled: git config core.hooksPath .githooks' }
}
$lock = Join-Path $DDRuntime 'job.lock'
if (Test-Path -LiteralPath $lock) {
    try { $s = [IO.File]::Open($lock, 'Open', 'ReadWrite', 'Read'); $s.Dispose() }
    catch { Say WARN 'another job is running' ((Get-Content -LiteralPath $lock -Raw).Trim()) }
}
if (Get-Process UnrealTournament -ErrorAction SilentlyContinue) { Say WARN 'UT is running' 'close it before a scan or render (the tools never close a UT they did not start)' }

# --- plan ------------------------------------------------------------------------------------------
if ($Plan) {
    try { $p = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json } catch { Say FAIL 'plan' "not valid JSON: $($_.Exception.Message)"; $p = $null }
    if ($p) {
        $shots = @($p.shots)
        if (-not $shots) { Say FAIL 'plan' 'no shots' }
        $dup = @($shots.id | Group-Object | Where-Object Count -gt 1 | ForEach-Object Name)
        if ($dup) { Say FAIL 'plan shot ids' "duplicates: $($dup -join ', ')" }
        $movie = @($shots | Where-Object { $_.kind -in 'first', 'cam' }).Count -gt 0
        if (-not $movie) { Say WARN 'plan format' 'no first/cam shots: not a Render-Movie plan, only basic checks done' }
        elseif (-not $p.music -or [double]$p.music.beat -le 0) { Say FAIL 'plan music' 'music.beat missing' }
        elseif (-not (Test-Path -LiteralPath $p.music.file)) { Say FAIL 'plan music' "file not found: $($p.music.file)" }
        else { Say OK 'plan music' (Split-Path $p.music.file -Leaf) }
        $bad = 0; $demos = @{}
        foreach ($s in $shots) {
            $why = @()
            if ($s.kind -notin 'first', 'cam') { continue }          # cards etc. belong to the assembler
            if ([double]$s.start -ge [double]$s.end) { $why += 'start >= end' }
            if ([double]$s.speed -le 0) { $why += 'speed <= 0' }
            if ([int]$s.beats -le 0 -or [double]$s.beats -ne [int]$s.beats) { $why += 'beats not a positive whole number' }
            if ($s.kind -eq 'first' -and -not $s.player) { $why += 'first-person shot without player' }
            if ($s.kind -eq 'cam' -and -not $s.cam) { $why += 'camera shot without cam' }
            if ($why) { $bad++; Say FAIL "shot $($s.id)" ($why -join ', ') }
            $demos[[string]$s.demo] = $true
        }
        foreach ($d in $demos.Keys) {
            try { [void](Resolve-DDDemo $d) } catch { $bad++; Say FAIL "demo $([IO.Path]::GetFileName($d))" $_.Exception.Message }
        }
        if (-not $bad -and $movie) { Say OK 'plan' "$($shots.Count) shots, $($demos.Count) demo(s) found" }
    }
}

Write-Host ''
if ($script:fails) { Write-Host "$($script:fails) problem(s) to fix, $($script:warns) warning(s)." -ForegroundColor Red; exit 1 }
Write-Host "Ready ($($script:warns) warning(s))." -ForegroundColor Green
