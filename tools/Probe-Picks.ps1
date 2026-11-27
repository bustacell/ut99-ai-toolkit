<# Probe every pick of a picks JSON ([{id, path, t, killer, victim}, ...], from find_headshots.py) -> OUTDIR\<id>.json.
   Skips existing ones. Then: python tools\hs_facts.py PICKS OUTDIR FACTS.json (docs\HEADSHOT.md). #>
param([Parameter(Mandatory)][string]$Picks, [Parameter(Mandatory)][string]$OutDir, [string[]]$Only)
$ErrorActionPreference = 'Continue'
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
$list = Get-Content -LiteralPath $Picks -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($p in $list) {
    if ($Only -and $p.id -notin $Only) { continue }
    $out = Join-Path $OutDir "$($p.id).json"
    if (Test-Path -LiteralPath $out) { "skip $($p.id)"; continue }
    try {
        & (Join-Path $PSScriptRoot 'Probe-Kill.ps1') -Demo $p.path -T $p.t -Killer $p.killer -Victim $p.victim -Out $out -Before 3.2 -After 1.0
        "$(Get-Date -Format HH:mm:ss) ok $($p.id)"
    } catch {
        "$(Get-Date -Format HH:mm:ss) FAILED $($p.id): $($_.Exception.Message)"
        try { Stop-UT } catch {}
    }
}
"done"
