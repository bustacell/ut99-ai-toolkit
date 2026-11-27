param()
$ErrorActionPreference = 'Stop'
$Tools = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:LVPS_ROOT) {
  $env:LVPS_ROOT = (Resolve-Path (Join-Path $Tools '..\..\..\..')).Path
}
$py = $null
foreach ($c in @('py','python','python3')) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) { throw 'Python 3 not found. Also: py -m pip install pillow' }
& $py "$Tools\assemble_final.py"
exit $LASTEXITCODE
