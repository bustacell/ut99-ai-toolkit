<#
.SYNOPSIS
  Switch UT's window size and frame cap between scanning and rendering.
  scan   = 640x480 window, FrameRateLimit 500 (more frames per demo second at 32x = finer rich data, faster start)
  render = 1920x1080 window, FrameRateLimit 120 (what Render-Clip / OBS expect)
  Only touches [WinDrv.WindowsClient]. UT must be closed (it rewrites the ini on exit).
  Scanning in scan mode with $env:UT_MINIMIZED = '1' keeps UT minimized, so the PC stays usable during long scans.
.EXAMPLE
  .\Set-UTVideoMode.ps1 scan
#>
param([Parameter(Mandatory)][ValidateSet('scan', 'render')][string]$Mode)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
if (Get-Process UnrealTournament -ErrorAction SilentlyContinue) { throw 'Close UT first (it rewrites UnrealTournament.ini on exit).' }
$ini = Join-Path $DDUT 'System\UnrealTournament.ini'
# A hard power-off while UT writes its ini can leave the file full of NUL bytes (UT then won't start).
if ([IO.File]::ReadAllBytes($ini) -contains 0) { throw "$ini contains NUL bytes (damaged by a crash). Restore it from backups\ first." }
$v = if ($Mode -eq 'scan') { @{ X = 640; Y = 480; F = '500.000000' } } else { @{ X = 1920; Y = 1080; F = '120.000000' } }
$c = Get-Content -LiteralPath $ini; $sec = ''; $n = 0
for ($i = 0; $i -lt $c.Count; $i++) {
    if ($c[$i] -match '^\[') { $sec = $c[$i] }
    if ($sec -ne '[WinDrv.WindowsClient]') { continue }
    if ($c[$i] -match '^WindowedViewportX=') { $c[$i] = "WindowedViewportX=$($v.X)"; $n++ }
    elseif ($c[$i] -match '^WindowedViewportY=') { $c[$i] = "WindowedViewportY=$($v.Y)"; $n++ }
    elseif ($c[$i] -match '^FrameRateLimit=') { $c[$i] = "FrameRateLimit=$($v.F)"; $n++ }
}
if ($n -ne 3) { throw "Expected 3 lines in [WinDrv.WindowsClient], found $n; ini not changed." }
[IO.File]::WriteAllLines($ini, $c, [Text.Encoding]::ASCII)
"UT video mode: $Mode ($($v.X)x$($v.Y), $($v.F) fps cap)"
