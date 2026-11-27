# LVPS Vol. 4 1080p finals (PowerShell).
# Examples:
#   .\render_finals.ps1
#   .\render_finals.ps1 -Device GPU
#   .\render_finals.ps1 -DryRun
param(
  [ValidateSet('CPU','GPU')][string]$Device = 'CPU',
  [switch]$DryRun,
  [switch]$SkipAssemble,
  [int]$Samples = 48
)
$ErrorActionPreference = 'Stop'
$Tools = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:LVPS_ROOT) {
  $env:LVPS_ROOT = (Resolve-Path (Join-Path $Tools '..\..\..\..')).Path
}
Write-Host "LVPS_ROOT=$($env:LVPS_ROOT)  Device=$Device"
$py = $null
foreach ($c in @('py','python','python3')) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) { throw 'Python 3 not found. Install Python 3.11+ and tick "Add python.exe to PATH".' }
$args = @("$Tools\render_finals.py", '--device', $Device, '--samples', "$Samples")
if ($DryRun) { $args += '--dry-run' }
if ($SkipAssemble) { $args += '--skip-assemble' }
& $py @args
exit $LASTEXITCODE
