<#
.SYNOPSIS
  Scan many demos (skips ones already scanned). Progress goes to logs\scan-all.log.
.EXAMPLE
  .\Scan-All.ps1 -ListFile ..\runtime\demos.txt      (list made by New-DemoList.ps1)
.NOTES
  Scans are stored by demo ID (DDConfig.ps1): the file name, or "<name>~<size>" when two different recordings
  share a file name, so each gets its own scan. A bare ambiguous name in the list can't be told apart: it is
  reported (FAIL, with the IDs to use) and the rest goes on.
#>
param([string]$ListFile, [string[]]$Demos, [double]$Speed = 32, [switch]$Force,
      [datetime]$RichAfter)   # with -Force: still skip demos whose .rich.log is newer than this
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
if ($ListFile) { $Demos = Get-Content -LiteralPath $ListFile | Where-Object { $_ } }
New-Item -ItemType Directory -Force (Join-Path $DDRoot 'logs'), (Join-Path $DDOut 'scans') | Out-Null
$log = Join-Path $DDRoot 'logs\scan-all.log'

$ix = Get-DDDemoIndex        # one pass over the demo folders, so IDs for thousands of demos stay fast
function Get-ListId([string]$d) {
    $stem = [IO.Path]::GetFileNameWithoutExtension($d)
    $e = $ix[[IO.Path]::GetFileName($d).ToLowerInvariant()]
    if (-not $e -or -not (Test-DDDemoAmbiguous $e)) { return $stem }
    if (Test-Path -LiteralPath $d) { return Get-DDDemoIdFor $d $e }   # same rules as everywhere (size, or size+hash)
    return $null                 # bare ambiguous name: which recording is meant is unknown
}
$i = 0
foreach ($d in $Demos) {
    $i++
    $name = Get-ListId $d
    if (-not $name) {
        $grp = $ix[[IO.Path]::GetFileName($d).ToLowerInvariant()]
        $ids = ($grp | ForEach-Object { Get-DDDemoIdFor $_.Path $grp }) -join ', '
        Add-Content $log "[$i/$($Demos.Count)] FAIL $d : ambiguous name, list the full path or one of the IDs $ids"; continue
    }
    $out = Join-Path $DDOut "scans\$name.events.json"
    if ((Test-Path -LiteralPath $out) -and -not $Force) { Add-Content $log "[$i/$($Demos.Count)] skip $name"; continue }
    $rich = Join-Path $DDOut "scans\$name.rich.log"
    if ($RichAfter -and (Test-Path -LiteralPath $rich) -and (Get-Item -LiteralPath $rich).LastWriteTime -gt $RichAfter) {
        Add-Content $log "[$i/$($Demos.Count)] skip (rich v2) $name"; continue
    }
    try {
        # NPLoader/ACE servers: UT sometimes hangs at demo start ("No demo data"); a fresh start usually works
        $try = 0; $r = $null
        while (-not $r) {
            try { $r = & (Join-Path $PSScriptRoot 'Scan-Demo.ps1') -Demo $d -Speed $Speed }
            catch {
                $try++
                if ($_.Exception.Message -notlike 'No demo data*' -or $try -ge 5) { throw }
                Add-Content $log "[$i/$($Demos.Count)] retry $try $name (UT hung at startup)"
                Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
                Stop-UT -Force; Start-Sleep 2     # only the UT this toolkit started
            }
        }
        Add-Content $log ("[{0}/{1}] ok   {2} len={3:n0}s wall={4}s kills={5}" -f $i, $Demos.Count, $name, $r.length, $r.wallSec, $r.kills)
    } catch {
        Add-Content $log "[$i/$($Demos.Count)] FAIL $name : $($_.Exception.Message)"
        if ($_.Exception.Message -like 'EXTERNAL DRIVE NOT CONNECTED*') { Add-Content $log 'STOPPED: external drive missing (rerun skips finished demos)'; break }
        Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
        try { Stop-UT -Force }
        catch { Add-Content $log "STOPPED: $($_.Exception.Message)"; break }   # e.g. a UT the user opened: never killed
        Start-Sleep 2
    }
}
Add-Content $log 'DONE'
