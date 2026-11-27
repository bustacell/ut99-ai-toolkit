# Renders a few small test frames of every map (end of build, combo approach, combo freeze) and a contact sheet.
#   .\Test-Frames.ps1 [-Keys pd,washme] [-Frames 520,300,560]
param([string[]]$Keys, [int[]]$Frames = @(520, 300, 560))
. "$PSScriptRoot\..\DDConfig.ps1"
$B = Resolve-DDPath $(if ($DDCfg.blender) { $DDCfg.blender } else { '..\blender\blender.exe' })
$S = Join-Path $PSScriptRoot 'gtm_holo.py'
$W = if ($env:UTDD_HOLO_WORK) { $env:UTDD_HOLO_WORK } else { Join-Path $DDOut 'work\hologram' }
$lineup = Get-Content -LiteralPath (Join-Path $W 'lineup.json') -Raw | ConvertFrom-Json
foreach ($e in $lineup) {
    if ($Keys -and ($Keys -notcontains $e.key)) { continue }
    $C = "$W\$($e.key)\config.json"
    $O = "$W\$($e.key)\test"
    if (Test-Path -LiteralPath $O) { Remove-Item -LiteralPath $O -Recurse -Force }
    for ($i = 0; $i -lt $Frames.Count; $i++) {
        $shot = if ($i -eq 0) { 'build' } else { 'combo' }
        $f = $Frames[$i]
        $log = & $B -b -P $S -- $C $shot "$O\$shot" --res 960 540 --frames $f ($f + 1) 2>&1
        $err = $log | Select-String 'Traceback|Error' | Select-Object -First 3
        $view = $log | Select-String 'END_VIEW' | Select-Object -First 1
        "$($e.key) $shot $f $view $err"
    }
}
python "$PSScriptRoot\contact_sheet.py" $W "$W\contact.png"
