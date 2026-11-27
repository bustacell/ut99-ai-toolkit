param(
  [Parameter(Mandatory=$true)][string]$Manifest,
  [string]$Output
)
$ErrorActionPreference = 'Stop'
$Tools = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = $null
foreach ($c in @('py','python','python3')) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) { throw 'Python 3 not found' }
$a = @("$Tools\reassemble_archive.py", $Manifest)
if ($Output) { $a += @('-o', $Output) }
& $py @a
exit $LASTEXITCODE
