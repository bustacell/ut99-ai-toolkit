# DDConfig.ps1 - shared settings for all PowerShell tools (dot-source it).
# Reads <toolkit>\config.json (created by setup\Setup.ps1). Paths in it may be relative to the toolkit
# folder (portable install on an external drive: the drive letter may change). Defines:
#   $DDRoot  toolkit folder           $DDCfg    the parsed config (paths resolved)
#   $DDUT    UT install folder        $DDPlayer your nickname
#   $DDOut   <toolkit>\output         $DDRuntime <toolkit>\runtime
# binDirs (portable ffmpeg / python / ...) are put in front of PATH for this process only.
$DDRoot = Split-Path -Parent $PSScriptRoot
$cfgFile = if ($env:DD_CONFIG) { $env:DD_CONFIG } else { Join-Path $DDRoot 'config.json' }   # DD_CONFIG: tests/CI
if (-not (Test-Path $cfgFile)) { throw "config.json missing in $DDRoot - run setup\Setup.ps1 first" }
$DDCfg = Get-Content $cfgFile -Raw | ConvertFrom-Json

function Resolve-DDPath([string]$p) {
    if (-not $p) { return $p }
    if ([IO.Path]::IsPathRooted($p)) { return $p }
    return [IO.Path]::GetFullPath((Join-Path $DDRoot $p))
}
$DDCfg.utRoot = Resolve-DDPath $DDCfg.utRoot
$DDCfg.obsDir = Resolve-DDPath $DDCfg.obsDir
$DDCfg.demoDirs = @($DDCfg.demoDirs | ForEach-Object { Resolve-DDPath $_ })
$DDBin = @($DDCfg.binDirs | Where-Object { $_ } | ForEach-Object { Resolve-DDPath $_ })
foreach ($b in $DDBin) {
    if (($env:PATH -split ';') -notcontains $b) { $env:PATH = "$b;$env:PATH" }
}

$DDUT = $DDCfg.utRoot
$DDPlayer = $DDCfg.player
$DDOut = Join-Path $DDRoot 'output'
$DDRuntime = Join-Path $DDRoot 'runtime'

function Get-DDDemoDirs { @(@($DDCfg.demoDirs) + (Join-Path $DDUT 'Demos') | Where-Object { $_ } | Select-Object -Unique) }

# Demo IDs: scans, moments and plans identify a demo by its ID = file name without .dem. Only when two DIFFERENT
# recordings share a file name (in two demo folders) does the ID get a suffix, so each gets its own scan:
#   "<name>~<size>"            the size tells them apart (the usual case)
#   "<name>~<size>-<sha8>"     two different recordings even have the same size: first 8 hex of the SHA-256
# Same name + same content = copies of one demo = one ID. Contents are only hashed when names collide AND sizes are
# equal. A bare ambiguous name is refused (never guessed). tools/ddconfig.py mirrors these rules.
$script:DDHashCache = @{}
function Get-DDDemoHash([string]$Path) {
    $f = Get-Item -LiteralPath $Path
    $k = "$($f.FullName)|$($f.Length)|$($f.LastWriteTimeUtc.Ticks)"
    if (-not $script:DDHashCache.ContainsKey($k)) {
        $script:DDHashCache[$k] = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.Substring(0, 8).ToLowerInvariant()
    }
    $script:DDHashCache[$k]
}

function Get-DDDemoMatches([string]$FileName) {
    @(foreach ($d in Get-DDDemoDirs) {
        # [IO.Path]::Combine, not Join-Path: Join-Path throws "drive not found" while an external drive is unplugged
        $p = [IO.Path]::Combine($d, $FileName)
        if (Test-Path -LiteralPath $p) { [pscustomobject]@{ Path = $p; Length = (Get-Item -LiteralPath $p).Length } }
    })
}

# Two entries of one group (same name) with the same size but different content?
function Test-DDDemoSameSizeClash($Entries, [long]$Length) {
    $same = @($Entries | Where-Object Length -eq $Length)
    $same.Count -gt 1 -and @($same | ForEach-Object { Get-DDDemoHash $_.Path } | Select-Object -Unique).Count -gt 1
}

function Test-DDDemoAmbiguous($Entries) {
    $Entries = @($Entries)
    if ($Entries.Count -lt 2) { return $false }
    $sizes = @($Entries | Select-Object -ExpandProperty Length -Unique)
    if ($sizes.Count -gt 1) { return $true }
    Test-DDDemoSameSizeClash $Entries $sizes[0]
}

function Get-DDDemoIdFor([string]$Path, $Entries) {
    # ID of the demo file at $Path, given all files with its name ($Entries: Path, Length)
    $stem = [IO.Path]::GetFileNameWithoutExtension($Path)
    if (-not (Test-Path -LiteralPath $Path) -or -not (Test-DDDemoAmbiguous $Entries)) { return $stem }
    $len = (Get-Item -LiteralPath $Path).Length
    if (Test-DDDemoSameSizeClash $Entries $len) { return "$stem~$len-$(Get-DDDemoHash $Path)" }
    "$stem~$len"
}

function Get-DDDemoId([string]$Path) { Get-DDDemoIdFor $Path (Get-DDDemoMatches ([IO.Path]::GetFileName($Path))) }

function Get-DDDemoIndex {
    # name (lower case, with .dem) -> list of @{ Path; Length } over all reachable demo folders
    $ix = @{}
    foreach ($d in Get-DDDemoDirs) {
        if (-not (Test-Path -LiteralPath $d)) { continue }
        foreach ($f in Get-ChildItem -LiteralPath $d -Filter *.dem -File -ErrorAction SilentlyContinue) {
            $k = $f.Name.ToLowerInvariant()
            if (-not $ix.ContainsKey($k)) { $ix[$k] = [Collections.Generic.List[object]]::new() }
            $ix[$k].Add([pscustomobject]@{ Path = $f.FullName; Length = $f.Length })
        }
    }
    $ix
}

function Resolve-DDDemo([string]$Demo) {
    # Full path of a demo given as a path, a bare file name or an ID "<name>~<size>[.dem]" (searched in config
    # demoDirs, then UT\Demos). A stored full path whose folder moved (e.g. an archive moved to another drive) is
    # found again by file name.
    if (Test-Path -LiteralPath $Demo) { return (Resolve-Path -LiteralPath $Demo).Path }
    $file = [IO.Path]::GetFileName($Demo)
    if ($file -notmatch '(?i)\.dem$') { $file += '.dem' }
    $hits = Get-DDDemoMatches $file
    if (-not $hits -and $file -match '^(?<n>.*)~(?<s>\d+)(-(?<h>[0-9a-f]{8}))?\.dem$') {   # an ID with suffix
        $n = $Matches.n; $s = [long]$Matches.s; $h = $Matches.h
        $cand = @(Get-DDDemoMatches "$n.dem" | Where-Object Length -eq $s)
        if ($h) { $cand = @($cand | Where-Object { (Get-DDDemoHash $_.Path) -eq $h }) }
        elseif (@($cand | ForEach-Object { Get-DDDemoHash $_.Path } | Select-Object -Unique).Count -gt 1) {
            throw "AMBIGUOUS DEMO ID: '$file' matches different recordings of the same size; use <name>~<size>-<hash>"
        }
        if ($cand) { return $cand[0].Path }
    }
    if ($hits.Count -gt 1 -and (Test-DDDemoAmbiguous $hits)) {
        throw "AMBIGUOUS DEMO NAME: '$file' is a different recording in several demo folders " +
              "($(($hits | ForEach-Object { "$($_.Path) [ID $(Get-DDDemoIdFor $_.Path $hits)]" }) -join '; ')). Give the ID or the full path."
    }
    if ($hits) { return $hits[0].Path }
    # Demo folders on an external drive: say so instead of "not found" (the drive is probably unplugged).
    # Scan-All stops on this message; never copy the demos elsewhere to work around it.
    $gone = @($DDCfg.demoDirs | Where-Object { $_ -and -not (Test-Path -LiteralPath $_) })
    if ($gone) { throw "EXTERNAL DRIVE NOT CONNECTED: '$Demo' not found and these demo folders are unreachable: $($gone -join ', '). Plug the drive in, then retry." }
    throw "Demo not found in config demoDirs: $Demo"
}
