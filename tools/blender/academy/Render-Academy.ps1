# Overnight renderer for TAUNT ACADEMY: builds and renders every chapter at 1920x1080.
# Resumable: frames that already exist are skipped (Blender placeholders), finished chapters are skipped.
# Keeps the PC awake (system, not display) only while this process runs; power settings are not changed.
param([string[]]$Chapters = @('L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'GRAD', 'C0', 'TITLE', 'BLOOP'))

$ErrorActionPreference = 'Stop'
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[void][Win32.Power]::SetThreadExecutionState([uint32]2147483649)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

$toolkit = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$cfgFile = Join-Path $toolkit 'config.json'
$cfg = if (Test-Path -LiteralPath $cfgFile) { Get-Content -LiteralPath $cfgFile -Raw | ConvertFrom-Json } else { $null }
$blender = if ($cfg -and $cfg.blender) { $cfg.blender } else { '..\blender\blender.exe' }
if (-not [IO.Path]::IsPathRooted($blender)) { $blender = [IO.Path]::GetFullPath((Join-Path $toolkit $blender)) }
if (-not (Test-Path -LiteralPath $blender)) { throw "Blender not found: $blender (set ""blender"" in config.json)" }
$engine = Join-Path $PSScriptRoot 'engine.py'
$root = Join-Path $toolkit 'output\work\academy\final'
$log = Join-Path $toolkit 'logs\render-academy.log'
New-Item -ItemType Directory -Force $root, (Split-Path $log) | Out-Null
$frames = @{ C0 = 62; TITLE = 120; L1 = 240; L2 = 216; L3 = 240; L4 = 192; L5 = 192; L6 = 216; GRAD = 192; BLOOP = 120 }

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Tee-Object -FilePath $log -Append }

Log "=== start: $($Chapters -join ', ')"
foreach ($ch in $Chapters) {
    $work = Join-Path $root $ch
    $fdir = Join-Path $work 'frames'
    $done = if (Test-Path -LiteralPath $fdir) { (Get-ChildItem -LiteralPath $fdir -Filter '*.png' | Where-Object Length -gt 0).Count } else { 0 }
    if ($done -ge $frames[$ch]) { Log "$ch already complete ($done frames)"; continue }
    $blend = Join-Path $work "$ch.blend"
    if (-not (Test-Path -LiteralPath $blend)) {
        Log "$ch build"
        & $blender -b -P $engine -- $ch $work *>> "$work-build.log"
        if (-not (Test-Path -LiteralPath $blend)) { Log "$ch BUILD FAILED (see $work-build.log)"; continue }
    }
    if (Test-Path -LiteralPath $fdir) {   # 0-byte placeholders from an interrupted run would be skipped forever
        Get-ChildItem -LiteralPath $fdir -Filter '*.png' | Where-Object Length -eq 0 | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
    }
    $t0 = Get-Date
    Log "$ch render ($done/$($frames[$ch]) present)"
    & $blender -b $blend -a *>> "$work-render.log"
    $done = (Get-ChildItem -LiteralPath $fdir -Filter '*.png' | Where-Object Length -gt 0).Count
    Log ("$ch finished: $done frames in {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes)
}
Log '=== all chapters done'
[void][Win32.Power]::SetThreadExecutionState([uint32]2147483648)   # ES_CONTINUOUS (release)
