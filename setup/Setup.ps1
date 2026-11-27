<#
.SYNOPSIS
  One-time setup of the UT99 AI Toolkit (Demo Director: game, OBS, music) on this PC.

.DESCRIPTION
  1. Checks the requirements (UT99 469 with uDemo, PowerShell 7, Python + numpy + Pillow, FFmpeg with libopenmpt, OBS).
  2. Writes config.json (your nickname, UT folder, demo folders, OBS folder).
  3. Backs up UnrealTournament.ini, User.ini and udemo.ini to backups\<timestamp>, then:
       - installs the DemoDirector helper package (System\DemoDirector.u + source in UT\DemoDirector\Classes,
         Models, Textures) and, if the Ultra Gore SSE mod is installed, System\DDUltraGore.u (headshot gore)
       - Console=DemoDirector.DDConsole, borderless 1920x1080 window, 120 fps limit, no decals
       - ScrollLock=exec <toolkit>\runtime\cmd.txt (the command channel the tools use)
       - udemo timing=0 (time-based playback; frame-based plays at the wrong speed)
       - DDMake.ini (only needed to rebuild DemoDirector.u from source)
  4. Creates the OBS profile + scene collection "UTVideo" (scene UT99 = game + game audio capture) and enables the
     OBS WebSocket server on port 4455 (keeps an existing password, otherwise generates one). The password is stored in
     runtime\obs-websocket.json and never printed.
  5. Exports UT's own soundtrack (Music\*.umx) to music\ as tracker modules for the movie soundtrack.

  Close UT and OBS before running. Running it again is safe (it re-applies the same settings).

  PORTABLE MODE (-PortableRoot): everything lives in one folder, e.g. on an external drive:
      X:\UTDD\UTDemoDirector   this toolkit (git clone)
      X:\UTDD\UT99             UT99 + OldUnreal 469 patch (a copy of your own game folder)
      X:\UTDD\OBS              OBS Studio portable zip (bin\64bit\obs64.exe)
      X:\UTDD\ffmpeg           FFmpeg full build zip (bin\ffmpeg.exe)
      X:\UTDD\python           standalone Python (python.exe) with numpy + Pillow
      X:\UTDD\pwsh             optional: PowerShell 7 zip
  Setup finds them by searching the folder. Paths in config.json are stored relative to the toolkit, so a
  different drive letter still works. OBS runs in portable mode (its settings in X:\UTDD\OBS\config), so nothing
  is written to %APPDATA% or the registry.

.EXAMPLE
  pwsh -File setup\Setup.ps1 -Player MyNick -PortableRoot X:\UTDD
.EXAMPLE
  pwsh -File setup\Setup.ps1 -Player MyNick -UTRoot C:\Games\UnrealTournament -DemoDirs C:\Games\UnrealTournament\Demos
#>
param(
    [Parameter(Mandatory)][string]$Player,
    [string]$PortableRoot,
    [string]$UTRoot = 'C:\Games\UnrealTournament',
    [string[]]$DemoDirs,
    [string]$ObsDir = 'C:\Program Files\obs-studio\bin\64bit',
    [ValidateSet('auto', 'x264', 'nvenc', 'amd', 'qsv')][string]$Encoder = 'auto',
    [switch]$SkipObs,
    [switch]$SkipMusic
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$ok = $true
function Say($m) { Write-Host $m }
function Bad($m) { Write-Host "  [missing] $m" -ForegroundColor Red; $script:ok = $false }
function Good($m) { Write-Host "  [ok] $m" -ForegroundColor Green }
function Rel([string]$p) { [IO.Path]::GetRelativePath($Root, $p) }   # stored relative in portable mode

$bin = @()
if ($PortableRoot) {
    $PortableRoot = (Resolve-Path $PortableRoot).Path
    Say "Portable mode: searching $PortableRoot"
    function Find1([string]$file, [string]$where = '') {
        Get-ChildItem $PortableRoot -Recurse -Filter $file -File -Depth 5 -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notlike "$Root*" -and $_.FullName -notmatch '\\(Scripts|Lib|site-packages|venv)\\' -and $_.FullName -like "*$where*" } |
            Sort-Object { $_.FullName.Length } | Select-Object -First 1
    }
    $ut = Find1 'UnrealTournament.exe' '\System\'
    if ($ut) { $UTRoot = Split-Path (Split-Path $ut.FullName) }
    $o = Find1 'obs64.exe' '\bin\64bit\'
    if ($o) { $ObsDir = Split-Path $o.FullName }
    foreach ($exe in 'ffmpeg.exe', 'python.exe', 'pwsh.exe') { $f = Find1 $exe; if ($f) { $bin += (Split-Path $f.FullName) } }
    foreach ($b in $bin) { $env:PATH = "$b;$env:PATH" }
    if (-not $Root.StartsWith($PortableRoot, 'OrdinalIgnoreCase')) { Write-Warning "The toolkit is not inside $PortableRoot; relative paths will break if the drive letter changes." }
    if (-not $DemoDirs) { $DemoDirs = @(Join-Path $UTRoot 'Demos') }
}

# ---------------------------------------------------------------- 1. requirements
Say 'Checking requirements'
if ($PSVersionTable.PSVersion.Major -lt 7) { Bad 'PowerShell 7+ (winget install Microsoft.PowerShell), then run this with pwsh' } else { Good "PowerShell $($PSVersionTable.PSVersion)" }
if ($Root -match '\s') { Bad "The toolkit folder must not contain spaces (UT's exec command can't handle them): $Root" } else { Good "toolkit folder $Root" }
$sys = Join-Path $UTRoot 'System'
if (-not (Test-Path (Join-Path $sys 'UnrealTournament.exe'))) { Bad "UT99 not found in $UTRoot (use -UTRoot)" }
else {
    $ver = (Get-Item (Join-Path $sys 'UnrealTournament.exe')).VersionInfo.ProductVersion
    if (-not (Test-Path (Join-Path $sys 'udemo.u'))) { Bad 'uDemo (System\udemo.u). Install the OldUnreal 469 patch, it ships uDemo.' }
    else { Good "UT99 in $UTRoot (exe version $ver, uDemo present)" }
    if (-not (Test-Path (Join-Path $sys 'UnrealTournament.ini'))) { Bad "System\UnrealTournament.ini not found. Start UT once (it creates its ini files), quit it, then run setup again." }
}
if (Get-Process UnrealTournament -ErrorAction SilentlyContinue) { Bad 'UT is running - close it first' }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Bad 'Python 3.10+ on PATH (winget install Python.Python.3.12)' }
else {
    $mods = & python -c "import importlib.util as u;print(','.join(m for m in ('numpy','PIL') if not u.find_spec(m)))"
    if ($mods) { Bad "Python packages: $mods  ->  python -m pip install numpy pillow   (uv-managed Python: uv pip install --python <python.exe> --system --break-system-packages numpy pillow)" }
    else { Good "$(& python --version) with numpy + Pillow ($((Get-Command python).Source))" }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { Bad 'ffmpeg + ffprobe on PATH (winget install Gyan.FFmpeg)' }
elseif (-not (& ffmpeg -hide_banner -formats 2>$null | Select-String libopenmpt)) { Bad 'FFmpeg without libopenmpt (needed for UT music). Use the full build: winget install Gyan.FFmpeg' }
else { Good 'FFmpeg with libopenmpt' }
if (-not $SkipObs) {
    if (-not (Test-Path (Join-Path $ObsDir 'obs64.exe'))) { Bad "OBS Studio 30+ not found in $ObsDir (winget install OBSProject.OBSStudio, or use -ObsDir)" } else { Good 'OBS Studio' }
    if (Get-Process obs64 -ErrorAction SilentlyContinue) { Bad 'OBS is running - close it first' }
}
if (-not (Test-Path 'C:\Windows\Fonts\bahnschrift.ttf')) { Bad 'Font Bahnschrift (ships with Windows 10/11) for the title cards' }
if (-not $ok) { throw 'Fix the missing items above and run setup again.' }

if (-not $DemoDirs) { $DemoDirs = @(Join-Path $UTRoot 'Demos') }
foreach ($d in $DemoDirs) { if (-not (Test-Path -LiteralPath $d)) { throw "Demo folder not found: $d" } }

# ---------------------------------------------------------------- 2. config + folders
foreach ($d in 'runtime', 'output', 'output\plans', 'output\scans', 'logs', 'recordings', 'music', 'backups') { New-Item -ItemType Directory -Force (Join-Path $Root $d) | Out-Null }
$UTRoot = (Resolve-Path $UTRoot).Path
$demoFull = @($DemoDirs | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
if ($PortableRoot) {
    $cfg = [ordered]@{ player = $Player; utRoot = (Rel $UTRoot); demoDirs = @($demoFull | ForEach-Object { Rel $_ }); obsDir = (Rel $ObsDir)
                       obsPortable = $true; binDirs = @($bin | ForEach-Object { Rel $_ }) }
} else {
    $cfg = [ordered]@{ player = $Player; utRoot = $UTRoot; demoDirs = $demoFull; obsDir = $ObsDir; obsPortable = $false; binDirs = @() }
}
# Merge, never replace: keep every key setup does not own (privateTerms, privateTermsFile, blender, assetsDir, ...)
# so a re-run can't silently weaken the privacy check or lose paths. The old file is backed up first.
$cfgPath = Join-Path $Root 'config.json'
$merged = [ordered]@{}
if (Test-Path -LiteralPath $cfgPath) {
    try { $old = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json }
    catch { throw "config.json exists but is not valid JSON; fix or move it, then run setup again ($($_.Exception.Message))" }
    $cfgBackup = Join-Path $Root ('backups\config.json.' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Copy-Item -LiteralPath $cfgPath $cfgBackup
    foreach ($prop in $old.PSObject.Properties) { $merged[$prop.Name] = $prop.Value }
    $kept = @($merged.Keys | Where-Object { -not $cfg.Contains($_) })
    Good "existing config.json backed up to backups\$(Split-Path $cfgBackup -Leaf)$(if ($kept) { '; kept: ' + ($kept -join ', ') })"
}
foreach ($k in $cfg.Keys) { $merged[$k] = $cfg[$k] }
$merged | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $cfgPath -Encoding UTF8
Good 'config.json written'
$runtime = Join-Path $Root 'runtime'
if (-not (Test-Path "$runtime\cmd.txt")) { Set-Content "$runtime\cmd.txt" 'ddstatus' -Encoding Ascii }

# ---------------------------------------------------------------- 3. UT
function Set-IniValue([string]$File, [string]$Section, [string]$Key, [string]$Value) {
    # Set Key=Value inside [Section] (first occurrence); append the key (or the section) if missing.
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $File)
    $s = $lines.IndexOf("[$Section]")
    if ($s -lt 0) { $lines.Add(''); $lines.Add("[$Section]"); $lines.Add("$Key=$Value") }
    else {
        $e = $s + 1
        while ($e -lt $lines.Count -and $lines[$e] -notmatch '^\[') { $e++ }
        $hit = -1
        for ($i = $s + 1; $i -lt $e; $i++) { if ($lines[$i] -match "^$([regex]::Escape($Key))=") { $hit = $i; break } }
        if ($hit -ge 0) { $lines[$hit] = "$Key=$Value" }
        else { $ins = $e; while ($ins -gt $s + 1 -and $lines[$ins - 1] -eq '') { $ins-- }; $lines.Insert($ins, "$Key=$Value") }
    }
    Set-Content -LiteralPath $File $lines -Encoding Ascii
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bk = Join-Path $Root "backups\$stamp"
New-Item -ItemType Directory -Force $bk | Out-Null
$utIni = Join-Path $sys 'UnrealTournament.ini'; $userIni = Join-Path $sys 'User.ini'; $udIni = Join-Path $sys 'udemo.ini'
foreach ($f in $utIni, $userIni, $udIni) { if (Test-Path $f) { Copy-Item $f $bk } }
Good "UT configs backed up to $bk"

Copy-Item (Join-Path $Root 'ut\DemoDirector.u') $sys -Force
foreach ($d in 'Classes', 'Models', 'Textures') {   # Models/Textures: the bullet-time bullet (tools\make_bullet_mesh.py)
    New-Item -ItemType Directory -Force (Join-Path $UTRoot "DemoDirector\$d") | Out-Null
    Copy-Item (Join-Path $Root "ut\DemoDirector\$d\*") (Join-Path $UTRoot "DemoDirector\$d") -Force
}
Good 'DemoDirector.u installed'
# Optional: impact gore from the Ultra Gore SSE mod (docs\HEADSHOT.md). DDUltraGore.u only loads if the mod is installed.
$withGore = Test-Path (Join-Path $sys 'NWUltraGoreSSEd.u')
if ($withGore) {
    Copy-Item (Join-Path $Root 'ut\DDUltraGore.u') $sys -Force
    New-Item -ItemType Directory -Force (Join-Path $UTRoot 'DDUltraGore\Classes') | Out-Null
    Copy-Item (Join-Path $Root 'ut\DDUltraGore\Classes\*.uc') (Join-Path $UTRoot 'DDUltraGore\Classes') -Force
    Good 'Ultra Gore found: DDUltraGore.u installed (headshot gore)'
}

Set-IniValue $utIni 'Engine.Engine' 'Console' 'DemoDirector.DDConsole'
foreach ($kv in @(('StartupFullscreen', 'False'), ('StartupBorderless', 'True'), ('WindowedViewportX', '1920'), ('WindowedViewportY', '1080'),
                  ('FrameRateLimit', '120.000000'), ('Decals', 'False'))) {
    Set-IniValue $utIni 'WinDrv.WindowsClient' $kv[0] $kv[1]
}
Set-IniValue $userIni 'Engine.Input' 'ScrollLock' "exec $runtime\cmd.txt"
if (-not (Test-Path $udIni)) { Set-Content $udIni '[udemo.DemoSettings]' -Encoding Ascii }
Set-IniValue $udIni 'udemo.DemoSettings' 'timing' '0'
Good 'UT settings applied (console, borderless 1920x1080, ScrollLock channel, uDemo timing)'

# DDMake.ini = UnrealTournament.ini + EditPackages udemo, DemoDirector[, NWUltraGoreSSEd, DDUltraGore]
# (for tools\Build-DD.ps1, or: cd System; .\ucc.exe make ini=DDMake.ini)
$mk = [Collections.Generic.List[string]](Get-Content $utIni)
$last = -1; for ($i = 0; $i -lt $mk.Count; $i++) { if ($mk[$i] -match '^EditPackages=') { $last = $i } }
if ($last -ge 0) {
    $add = @('udemo', 'DemoDirector')
    if ($withGore) { $add += 'NWUltraGoreSSEd', 'DDUltraGore' }   # DDUltraGore after DemoDirector and the mod
    foreach ($p in $add) { if (-not ($mk -contains "EditPackages=$p")) { $last++; $mk.Insert($last, "EditPackages=$p") } }
    Set-Content (Join-Path $sys 'DDMake.ini') $mk -Encoding Ascii
}

# ---------------------------------------------------------------- 4. OBS
if (-not $SkipObs) {
    if ($PortableRoot) {
        # OBS portable mode: portable_mode.txt next to bin\ makes OBS keep its settings in <OBS>\config\obs-studio
        $obsHome = Split-Path (Split-Path $ObsDir)
        if (-not (Test-Path (Join-Path $obsHome 'portable_mode.txt'))) { Set-Content (Join-Path $obsHome 'portable_mode.txt') '' }
        $obs = Join-Path $obsHome 'config\obs-studio'
    } else { $obs = Join-Path $env:APPDATA 'obs-studio' }
    $prof = Join-Path $obs 'basic\profiles\UTVideo'; $scenes = Join-Path $obs 'basic\scenes'
    New-Item -ItemType Directory -Force $prof, $scenes | Out-Null
    if ($Encoder -eq 'auto') {
        $gpu = (Get-CimInstance Win32_VideoController | ForEach-Object Name) -join ' '
        $Encoder = if ($gpu -match 'NVIDIA') { 'nvenc' } elseif ($gpu -match 'AMD|Radeon') { 'amd' } elseif ($gpu -match 'Intel') { 'qsv' } else { 'x264' }
    }
    $rec = (Join-Path $Root 'recordings') -replace '\\', '/'
    (Get-Content (Join-Path $PSScriptRoot 'obs\UTVideo-profile.ini')) -replace '^(FilePath|RecFilePath)=.*', "`$1=$rec" -replace '^RecEncoder=amd$', "RecEncoder=$Encoder" |
        Set-Content (Join-Path $prof 'basic.ini') -Encoding UTF8
    $sc = Join-Path $scenes 'UTVideo.json'
    if (Test-Path $sc) { Copy-Item $sc (Join-Path $bk 'obs-UTVideo-scene.json') }
    Copy-Item (Join-Path $PSScriptRoot 'obs\UTVideo-scene.json') $sc -Force

    $wsDir = Join-Path $obs 'plugin_config\obs-websocket'
    New-Item -ItemType Directory -Force $wsDir | Out-Null
    $wsFile = Join-Path $wsDir 'config.json'
    $ws = if (Test-Path $wsFile) { Copy-Item $wsFile (Join-Path $bk 'obs-websocket-config.json'); Get-Content $wsFile -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
    $pw = $ws.server_password
    if (-not $pw) { $pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 20 | ForEach-Object { [char]$_ }) }
    $port = if ($ws.server_port) { [int]$ws.server_port } else { 4455 }
    $new = [ordered]@{ alerts_enabled = $false; auth_required = $true; first_load = $false; server_enabled = $true; server_password = $pw; server_port = $port }
    $new | ConvertTo-Json | Set-Content $wsFile -Encoding UTF8
    [ordered]@{ host = 'localhost'; port = $port; password = $pw } | ConvertTo-Json | Set-Content (Join-Path $runtime 'obs-websocket.json') -Encoding UTF8
    Good "OBS profile + scene 'UTVideo' (encoder $Encoder), WebSocket on port $port (password in runtime\obs-websocket.json)"
}

# ---------------------------------------------------------------- 5. music
if (-not $SkipMusic) {
    $mdir = Join-Path $Root 'music'
    $tmp = Join-Path $env:TEMP "utdd-music-$stamp"
    New-Item -ItemType Directory -Force $tmp | Out-Null
    Push-Location $sys
    try {
        foreach ($u in Get-ChildItem (Join-Path $UTRoot 'Music') -Filter *.umx) {
            & .\ucc.exe batchexport $u.FullName music it $tmp 2>&1 | Out-Null
        }
    } finally { Pop-Location }
    $n = 0
    foreach ($f in Get-ChildItem $tmp -File) {
        $h = [IO.File]::ReadAllBytes($f.FullName)
        $ext = if ([Text.Encoding]::ASCII.GetString($h, 0, 4) -eq 'IMPM') { 'it' }
               elseif ($h.Length -gt 48 -and [Text.Encoding]::ASCII.GetString($h, 44, 4) -eq 'SCRM') { 's3m' }
               elseif ([Text.Encoding]::ASCII.GetString($h, 0, 15) -eq 'Extended Module') { 'xm' }
               else { 'mod' }
        Move-Item $f.FullName (Join-Path $mdir "$($f.BaseName).$ext") -Force; $n++
    }
    Remove-Item $tmp -Recurse -Force
    Good "$n UT soundtrack modules exported to music\"
}

Say ''
Say 'Setup done. Next:'
Say "  cd $Root\tools"
Say '  .\New-DemoList.ps1                        # which demos are playable'
Say '  .\Render-Clip.ps1 -Demo <a demo>.dem -Start 60 -Duration 10 -Player <nick> -Camera first   # smoke test'
Say 'Or open the folder in Claude Code and run /frag-movie.'
