<#
.SYNOPSIS
  Offline PowerShell checks (no game, no OBS): every script and module parses, and the render-resume decision
  (Render-Movie.ps1) reuses only valid, unchanged shots. Exit code 0 = all passed. Runs on Windows and in CI (pwsh).
#>
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$fail = 0
function Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
    if ($Ok) { Write-Host "ok   $Name" } else { Write-Host "FAIL $Name $Detail"; $script:fail++ }
}

# 1. every .ps1 / .psm1 parses
foreach ($f in Get-ChildItem $repo -Recurse -File -Include *.ps1, *.psm1 | Where-Object { $_.FullName -notmatch '[\\/](\.git|output|runtime|assets|music|recordings|backups|logs)[\\/]' }) {
    $err = $null
    [void][Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$err)
    Check "parse $($f.FullName.Substring($repo.Length + 1))" (-not $err) ($err | Select-Object -First 1)
}

# 2. render resume: load only the helper functions of Render-Movie.ps1 (the script itself needs the game)
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $repo 'tools/Render-Movie.ps1'), [ref]$null, [ref]$null)
$ast.FindAll({ $args[0] -is [Management.Automation.Language.FunctionDefinitionAst] }, $false) |
    ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$w = Join-Path ([IO.Path]::GetTempPath()) ("ut99kit-ps-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force $w | Out-Null
try {
    $out = Join-Path $w 's01.mp4'; $kf = Join-Path $w 's01.inputs.txt'
    $a = @{ Demo = 'd.dem'; Start = '10'; End = '12'; Speed = 1.0; Output = $out; KeepGameOpen = $true; NoGore = $true
            HudMode = 1; Camera = 'cam'; Cam = 'mode=orbit r=300'; Tags = @('YourNick') }
    $k = Get-ShotKey $a
    Check 'key ignores Output/KeepGameOpen/Reuse' ($k -eq (Get-ShotKey ($a.Clone() + @{ Reuse = $true })))
    Set-Content $out 'x'; Set-Content ([IO.Path]::ChangeExtension($out, '.json')) '{"valid":true}'
    Check 'legacy valid clip is reused and adopted' ($null -eq (Test-ShotReusable $out $kf $k) -and (Test-Path $kf))
    Check 'unchanged shot is reused' ($null -eq (Test-ShotReusable $out $kf $k))
    $b = $a.Clone(); $b.Cam = 'mode=orbit r=500'
    Check 'edited shot is re-rendered' ((Test-ShotReusable $out $kf (Get-ShotKey $b)) -eq 'shot changed in the plan')
    Set-Content ([IO.Path]::ChangeExtension($out, '.json')) '{"valid":false}'
    Check 'invalid clip is re-rendered' ((Test-ShotReusable $out $kf $k) -eq 'report says invalid')
    Move-ShotAside $out 'stale'
    Check 'moved aside, not deleted' ((Test-Path (Join-Path $w 's01.stale.mp4')) -and -not (Test-Path $out))

    # pre-assembly gate: checks EVERY shot (also with -AssembleOnly / after -Only), moves stale ones aside
    function F([double]$x) { $x.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture) }
    $plan = @(
        [pscustomobject]@{ id = 'g1'; kind = 'cam'; demo = 'd.dem'; start = 10; end = 12; speed = 1; hud = 1; cam = 'mode=orbit' },
        [pscustomobject]@{ id = 'g2'; kind = 'cam'; demo = 'd.dem'; start = 20; end = 22; speed = 1; hud = 1; cam = 'mode=orbit' })
    foreach ($s in $plan) {
        $o = Join-Path $w "$($s.id).mp4"; Set-Content $o 'x'; Set-Content ([IO.Path]::ChangeExtension($o, '.json')) '{"valid":true}'
        Set-Content (Join-Path $w "$($s.id).inputs.txt") (Get-ShotKey (New-ShotArgs $s $o))
    }
    $plan[1].start = 21                                       # edit shot g2 after it was rendered
    $log = $null
    $moved = Invoke-AssemblyGate $plan $w
    Check 'gate moves only the edited shot aside' ($moved -eq 1 -and (Test-Path (Join-Path $w 'g1.mp4')) -and (Test-Path (Join-Path $w 'g2.stale.mp4')) -and -not (Test-Path (Join-Path $w 'g2.mp4')))
} finally { Remove-Item -LiteralPath $w -Recurse -Force }

# 3. demo IDs (DDConfig.ps1): plain file name, or "<name>~<size>" for different recordings with the same name
$w = Join-Path ([IO.Path]::GetTempPath()) ("ut99kit-ids-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$A = Join-Path $w 'ArchiveA'; $B = Join-Path $w 'ArchiveB'; $ut = Join-Path $w 'UT'
New-Item -ItemType Directory -Force $A, $B, (Join-Path $ut 'Demos') | Out-Null
try {
    [IO.File]::WriteAllBytes((Join-Path $A 'shared.dem'), [byte[]]::new(10))
    [IO.File]::WriteAllBytes((Join-Path $B 'shared.dem'), [byte[]]::new(20))
    [IO.File]::WriteAllBytes((Join-Path $A 'copy.dem'), [byte[]]::new(7))
    [IO.File]::WriteAllBytes((Join-Path $B 'copy.dem'), [byte[]]::new(7))
    [IO.File]::WriteAllBytes((Join-Path $A 'plain.dem'), [byte[]]::new(3))
    [IO.File]::WriteAllBytes((Join-Path $A 'twin.dem'), [byte[]](@(97) * 12))     # same name, same size,
    [IO.File]::WriteAllBytes((Join-Path $B 'twin.dem'), [byte[]](@(98) * 12))     # different content
    @{ player = 'YourNick'; utRoot = $ut; demoDirs = @($A, $B); binDirs = @(); obsDir = ''; obsPortable = $false } |
        ConvertTo-Json | Set-Content (Join-Path $w 'config.json')
    $env:DD_CONFIG = Join-Path $w 'config.json'
    . (Join-Path $repo 'tools/DDConfig.ps1')
    Check 'ID: shared name gets size suffix' ((Get-DDDemoId (Join-Path $A 'shared.dem')) -eq 'shared~10' -and (Get-DDDemoId (Join-Path $B 'shared.dem')) -eq 'shared~20')
    Check 'ID: identical copies keep the plain ID' ((Get-DDDemoId (Join-Path $B 'copy.dem')) -eq 'copy')
    Check 'ID: unique name stays plain' ((Get-DDDemoId (Join-Path $A 'plain.dem')) -eq 'plain')
    Check 'resolve ID with suffix' ((Resolve-DDDemo 'shared~20.dem') -eq (Join-Path $B 'shared.dem') -and (Resolve-DDDemo 'shared~10') -eq (Join-Path $A 'shared.dem'))
    Check 'resolve plain name' ((Resolve-DDDemo 'plain.dem') -eq (Join-Path $A 'plain.dem'))
    $err = try { Resolve-DDDemo 'shared.dem'; '' } catch { $_.Exception.Message }
    Check 'bare shared name is refused with the IDs' ($err -like 'AMBIGUOUS DEMO NAME*' -and $err -like '*shared~10*' -and $err -like '*shared~20*')
    $ta = Get-DDDemoId (Join-Path $A 'twin.dem'); $tb = Get-DDDemoId (Join-Path $B 'twin.dem')
    Check 'same size, different content: hash suffix' ($ta -match '^twin~12-[0-9a-f]{8}$' -and $tb -match '^twin~12-[0-9a-f]{8}$' -and $ta -ne $tb)
    Check 'hash IDs resolve to the right file' ((Resolve-DDDemo "$ta.dem") -eq (Join-Path $A 'twin.dem') -and (Resolve-DDDemo $tb) -eq (Join-Path $B 'twin.dem'))
    $err = try { Resolve-DDDemo 'twin~12.dem'; '' } catch { $_.Exception.Message }
    Check 'size-only ID of same-size twins is refused' ($err -like 'AMBIGUOUS DEMO ID*')
    Check 'identical same-size copies stay one plain ID' ((Get-DDDemoId (Join-Path $A 'copy.dem')) -eq 'copy')
} finally { Remove-Item Env:DD_CONFIG -ErrorAction SilentlyContinue; Remove-Item -LiteralPath $w -Recurse -Force }

if ($fail) { Write-Host "$fail check(s) failed"; exit 1 }
Write-Host 'all PowerShell checks passed'
