<#
.SYNOPSIS
  List all playable demos in the config demoDirs into runtime\demos.txt (input for Scan-All.ps1).
  Skips empty stub demos (< 200 KB) and demos whose map is not installed (Maps\ or Cache\cache.ini).
.EXAMPLE
  .\New-DemoList.ps1
#>
param([string]$Out, [int]$MinKB = 200)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
if (-not $Out) { $Out = Join-Path $DDRuntime 'demos.txt' }

# installed maps: Maps\*.unr plus downloaded maps in Cache (cache.ini lines "GUID=Name.unr")
$maps = @{}
Get-ChildItem (Join-Path $DDUT 'Maps') -Filter *.unr -ErrorAction SilentlyContinue | ForEach-Object { $maps[$_.BaseName.ToLower()] = 1 }
$ci = Join-Path $DDUT 'Cache\cache.ini'
if (Test-Path $ci) {
    foreach ($l in Get-Content $ci) { if ($l -match '^[0-9A-Fa-f]{32}=(.+?)\.unr$') { $maps[$Matches[1].ToLower()] = 1 } }
}

$ok = @(); $stub = 0; $nomap = @()
foreach ($dir in @($DDCfg.demoDirs)) {
    foreach ($f in Get-ChildItem -LiteralPath $dir -Filter *.dem -File -ErrorAction SilentlyContinue) {
        if ($f.Length -lt $MinKB * 1KB) { $stub++; continue }
        if ($f.FullName -match '\s') { Write-Warning "skipped (space in path, UT can't play it): $($f.FullName)"; continue }
        $map = $f.Name -replace '_\d{1,2}-\d{1,2}_\d{1,2}-\d{1,2}-\d{1,2}(-\d)?\.dem$', ''
        if (-not $maps.ContainsKey($map.ToLower())) { $nomap += $map; continue }
        $ok += $f.FullName
    }
}
New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
$ok | Set-Content -LiteralPath $Out -Encoding UTF8
"{0} demos -> {1}" -f $ok.Count, $Out
if ($stub) { "skipped $stub empty stub demos (< $MinKB KB)" }
if ($nomap) { "skipped {0} demos with missing maps: {1}" -f $nomap.Count, (($nomap | Sort-Object -Unique) -join ', ') }
