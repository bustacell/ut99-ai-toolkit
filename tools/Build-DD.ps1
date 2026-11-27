<#
.SYNOPSIS
  Rebuild the helper packages from the sources in this repo: ut\DemoDirector (classes + bullet models/textures) and,
  if the Ultra Gore SSE mod is installed, ut\DDUltraGore. Copies the sources into the UT folder, runs
  "ucc make ini=DDMake.ini" there and copies the built .u files back into ut\.
.NOTES
  UT must be closed (it is stopped if running). The previous DemoDirector.u is restored if the build fails.
  DDMake.ini is created by setup\Setup.ps1 (EditPackages ... udemo, DemoDirector[, NWUltraGoreSSEd, DDUltraGore]).
  Regenerate the bullet meshes/textures first with "python tools\make_bullet_mesh.py ut\DemoDirector" if you changed them.
#>
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
if (Get-UTProcess) { Stop-UT; Start-Sleep 1 }
$sys = Join-Path $DDUT 'System'
$src = Join-Path $DDRoot 'ut'
$withGore = Test-Path -LiteralPath (Join-Path $sys 'NWUltraGoreSSEd.u')
foreach ($d in 'Classes', 'Models', 'Textures') {
    $from = Join-Path $src "DemoDirector\$d"
    if (Test-Path -LiteralPath $from) {
        New-Item -ItemType Directory -Force (Join-Path $DDUT "DemoDirector\$d") | Out-Null
        Copy-Item (Join-Path $from '*') (Join-Path $DDUT "DemoDirector\$d") -Force
    }
}
if ($withGore) {
    New-Item -ItemType Directory -Force (Join-Path $DDUT 'DDUltraGore\Classes') | Out-Null
    Copy-Item (Join-Path $src 'DDUltraGore\Classes\*.uc') (Join-Path $DDUT 'DDUltraGore\Classes') -Force
}
$mk = Join-Path $sys 'DDMake.ini'
if (-not (Test-Path -LiteralPath $mk)) { throw 'System\DDMake.ini missing - run setup\Setup.ps1' }
if ($withGore -and -not (Select-String -LiteralPath $mk -Pattern '^EditPackages=DDUltraGore$' -Quiet)) {
    Write-Warning 'Ultra Gore is installed but DDMake.ini has no EditPackages=DDUltraGore: rerun setup\Setup.ps1 to add it'
}
Push-Location $sys
try {
    if (Test-Path -LiteralPath .\DemoDirector.u) { Copy-Item -LiteralPath .\DemoDirector.u -Destination .\DemoDirector.u.prev -Force; Remove-Item -LiteralPath .\DemoDirector.u }
    # DDUltraGore is compiled against DemoDirector: rebuild it too
    if (Test-Path -LiteralPath .\DDUltraGore.u) { Remove-Item -LiteralPath .\DDUltraGore.u }
    $out = & .\ucc.exe make ini=DDMake.ini 2>&1
    $out | Select-String -Pattern 'Error|Warning|Success|Failure' | ForEach-Object { $_.Line }
    if (-not (Test-Path -LiteralPath .\DemoDirector.u)) { Copy-Item -LiteralPath .\DemoDirector.u.prev -Destination .\DemoDirector.u; throw 'Build failed (previous package restored)' }
    Copy-Item -LiteralPath .\DemoDirector.u -Destination (Join-Path $src 'DemoDirector.u') -Force
    if (Test-Path -LiteralPath .\DDUltraGore.u) { Copy-Item -LiteralPath .\DDUltraGore.u -Destination (Join-Path $src 'DDUltraGore.u') -Force }
} finally { Pop-Location }
