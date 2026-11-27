# Build a .t3d into a playable .unr without the UnrealEd GUI (ucc exec = editor commands in a minimal editor).
# UT must not hold the target map open. Example: .\Build-Map.ps1 -T3D C:\x\test.t3d -Map CTF-DDTest
# -CustomTextures <dir>: every *.bmp in it (8-bit palettized) is imported into the map's own package (MyLevel),
# named after the file, so the map ships as a single .unr.
param([Parameter(Mandatory)][string]$T3D, [Parameter(Mandatory)][string]$Map,
      [string[]]$TexturePackages = @('Lian-X'), [string]$CustomTextures,
      # optional FORMAT= for TEXTURE IMPORT (e.g. BC7); untested which renderers use it, so the default is to
      # pass pre-dithered 8-bit BMPs (to_p8.py) that the engine keeps as P8
      [string]$CustomTextureFormat = '',
      [string]$Bsp = 'OPTIMAL BALANCE=15 PORTALBIAS=70')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\DDConfig.ps1')
Import-Module (Join-Path $PSScriptRoot '..\UTDirector.psm1') -Force
$sys = Join-Path $DDUT 'System'
# A running UT (e.g. left open by Render-Path / a demo) holds the map file: ucc then reports "Success" but cannot
# replace the .unr, and every later step silently uses the old map. Close it, and check the file really changed.
if (Get-UTProcess) { Stop-UT; Start-Sleep 1 }
$buildStart = Get-Date
$t3dFull = (Resolve-Path -LiteralPath $T3D).Path
$lines = @()
foreach ($t in $TexturePackages) { $lines += "OBJ LOAD FILE=..\Textures\$t.utx" }
if ($CustomTextures) {
    foreach ($f in Get-ChildItem -LiteralPath $CustomTextures | Where-Object Extension -in '.bmp', '.png') {
        $fmt = if ($CustomTextureFormat) { " FORMAT=$CustomTextureFormat" } else { '' }
        $lines += "TEXTURE IMPORT FILE=$($f.FullName) NAME=$($f.BaseName) PACKAGE=MyLevel MIPS=ON$fmt"
    }
}
$lines += @(
    "MAP IMPORT FILE=$t3dFull",
    'MAP REBUILD',
    "BSP REBUILD $Bsp ZONES",   # ZONES is required, else every actor is "out of the world"
    'PATHS DEFINE',
    'LIGHT APPLY',
    # LIGHT APPLY opens a "temporary viewport" whose Camera actor keeps a pointer to it (Camera.Player); when the
    # viewport goes away the save GPFs in SavePackage on that pointer. ACTOR SELECT/DELETE never catches the camera
    # (earlier "successes" were luck) and CAMERA CLOSE does not help; detaching the pointer does, reliably.
    'SET Camera Player None',
    "MAP SAVE FILE=..\Maps\$Map.unr")
$exec = Join-Path ([IO.Path]::GetTempPath()) "dd-mapbuild-$Map.txt"
Set-Content -LiteralPath $exec $lines -Encoding Ascii
Push-Location $sys
try {
    $out = & .\UCC.exe exec $exec 2>&1 | ForEach-Object { "$_" }
} finally { Pop-Location }
$out | Select-String -Pattern 'Polys:|reachspecs in|Moving|Success|error|Critical|History' | Select-Object -Last 8 | ForEach-Object Line
if (-not ($out -match '^Success')) { throw "Map build failed, see $sys\UCC.log" }
$unr = Join-Path $DDUT "Maps\$Map.unr"
if (-not (Test-Path -LiteralPath $unr) -or (Get-Item -LiteralPath $unr).LastWriteTime -lt $buildStart) {
    throw "ucc reported Success but $unr was not replaced (file in use?)"
}
