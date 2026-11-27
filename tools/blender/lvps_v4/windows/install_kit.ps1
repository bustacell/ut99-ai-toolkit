# Reassemble the kit zip(s) and merge into C:\Games\UTGrokBot without overwriting
# existing Vol. 1-3 finals that already match (or that differ — those are reported, not overwritten).
param(
  [string]$TransferDir = "$env:USERPROFILE\UTGrokBot_transfer",
  [string]$Dest = "C:\Games\UTGrokBot",
  [string]$Python = ""
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
  foreach ($c in @('py','python','python3')) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $Python = $c; break }
  }
}
if (-not $Python) { throw 'Python 3 not found. Install Python 3.11+ (Add to PATH) and Pillow: py -m pip install pillow' }

New-Item -ItemType Directory -Force -Path $TransferDir, $Dest | Out-Null

# Find part manifests in the transfer dir (kit_core and frames, or a combined archive)
$mans = Get-ChildItem -Path $TransferDir -Filter *.parts.json
if (-not $mans) { throw "No *.parts.json found in $TransferDir" }

$reasm = $null
# After first extract we'll have tools; until then use a copy of reassemble next to the parts if present
foreach ($m in $mans) {
  Write-Host "REASSEMBLE $($m.Name)"
  $script = Join-Path $TransferDir "reassemble_archive.py"
  if (-not (Test-Path $script)) { throw "reassemble_archive.py must sit next to the parts in $TransferDir" }
  & $Python $script $m.FullName
  if ($LASTEXITCODE -ne 0) { throw "reassemble failed for $($m.Name)" }
}

# Extract zips into a temp extract folder, then merge
$extract = Join-Path $TransferDir "extracted"
New-Item -ItemType Directory -Force -Path $extract | Out-Null
Get-ChildItem -Path $TransferDir -Filter *.zip | ForEach-Object {
  Write-Host "EXTRACT $($_.Name)"
  Expand-Archive -Path $_.FullName -DestinationPath $extract -Force
}

# The zip is expected to contain a top-level UTGrokBot\ or the kit root files directly
$src = $extract
if (Test-Path (Join-Path $extract "UTGrokBot")) { $src = Join-Path $extract "UTGrokBot" }
elseif (Test-Path (Join-Path $extract "LVPS_ROOT.marker")) { $src = $extract }
elseif (Test-Path (Join-Path $extract "assets")) { $src = $extract }

Write-Host "MERGE $src  ->  $Dest  (skip identical; never overwrite different existing files)"
$copied = 0; $skipped = 0; $conflict = 0
Get-ChildItem -Path $src -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($src.Length).TrimStart('\','/')
  $target = Join-Path $Dest $rel
  $tDir = Split-Path $target -Parent
  if (-not (Test-Path $tDir)) { New-Item -ItemType Directory -Force -Path $tDir | Out-Null }
  if (-not (Test-Path $target)) {
    Copy-Item $_.FullName $target
    $copied++
  } elseif ($_.Length -eq (Get-Item $target).Length) {
    $h1 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    $h2 = (Get-FileHash $target -Algorithm SHA256).Hash
    if ($h1 -eq $h2) { $skipped++ }
    else {
      $conflict++
      Write-Warning "CONFLICT (not overwritten): $rel"
      $log = Join-Path $TransferDir "merge_conflicts.txt"
      Add-Content $log "$rel  kit=$h1  existing=$h2"
    }
  } else {
    $conflict++
    Write-Warning "CONFLICT size (not overwritten): $rel  kit=$($_.Length) existing=$((Get-Item $target).Length)"
    $log = Join-Path $TransferDir "merge_conflicts.txt"
    Add-Content $log "$rel  kit_size=$($_.Length) existing=$((Get-Item $target).Length)"
  }
}
Write-Host "DONE copied=$copied skipped_identical=$skipped conflicts=$conflict"
Write-Host "Set  `$env:LVPS_ROOT = '$Dest'   then see the README in $Dest"
