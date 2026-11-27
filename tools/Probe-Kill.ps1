<#
.SYNOPSIS
  Find the exact demo time and positions of a kill (for bullet-time shots).
  Plays [T-Before, T+After] at -Speed with "ddprobe" on and writes every PROBE / CARC / STR / DEATH line to a JSON file.
.EXAMPLE
  .\Probe-Kill.ps1 -Demo DM-Example_07-28_23-16-13.dem -T 222.2 -Killer YourNick -Victim Bounce -Out probe.json
.NOTES
  No recording, OBS is not needed. The game window shows the demo in slow motion meanwhile.
  Several kills of one demo: pass -Reuse -KeepGameOpen and ascending -T.
#>
param(
    [Parameter(Mandatory)][string]$Demo,
    [Parameter(Mandatory)][double]$T,
    [Parameter(Mandatory)][string]$Killer,
    [Parameter(Mandatory)][string]$Victim,
    [Parameter(Mandatory)][string]$Out,
    [double]$Before = 1.6,
    [double]$After = 0.8,
    [double]$Speed = 0.25,
    [switch]$Reuse,
    [switch]$KeepGameOpen
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
Import-Module (Join-Path $PSScriptRoot 'UTDirector.psm1') -Force
$demoPath = Resolve-DDDemo $Demo
Set-UTKeepAwake
if ($Reuse -and (Get-UTProcess)) { Reset-UTLogCursor } else { [void](Start-UTDemo $demoPath); Start-Sleep 1 }
$st = Get-UTStatus
if (-not $st) { throw 'No status from DemoDirector helper' }
if ($st.paused -ne '0') { Send-UTCommand 'pause' }
$t0 = [math]::Max(0, $T - $Before)
$seek = Invoke-UTSeek ([math]::Max(0, $t0 - 1))
$ids = @{}
foreach ($pl in (Get-UTPlayers)) { if ($pl.spec -ne 'True' -or -not $ids.ContainsKey($pl.name)) { $ids[$pl.name] = [int]$pl.id } }
if (-not $ids.ContainsKey($Killer)) { throw "Killer '$Killer' not in demo" }
if (-not $ids.ContainsKey($Victim)) { throw "Victim '$Victim' not in demo" }
$k = $ids[$Killer]; $v = $ids[$Victim]
Reset-UTLogCursor
Send-UTCommand "slomo $($Speed.ToString($inv))", 'ddramp off', 'ddbullet off', "ddprobe k=$k v=$v" -SettleMs 100
$lines = New-Object System.Collections.Generic.List[string]
$sw = [Diagnostics.Stopwatch]::StartNew()
$maxWall = ($Before + $After + 3) / $Speed + 20
$cur = 0.0
while ($cur -lt $T + $After) {
    Start-Sleep -Milliseconds 250
    foreach ($l in (Read-UTLogNew)) {
        if ($l -match '^DemoDirector: DD\|(PROBE|CARC|STR|DEATH|STATE)\|t=([\d\.]+)\|') {
            $cur = [double]::Parse($Matches[2], $inv)
            if ($Matches[1] -ne 'STATE') { $lines.Add($l.Substring(17)) }
        }
    }
    if ($sw.Elapsed.TotalSeconds -gt $maxWall) { throw "Probe did not reach $($T + $After) (at $cur)" }
}
Send-UTCommand 'ddprobe off', 'slomo 1' -SettleMs 100
if (-not $KeepGameOpen) { Stop-UT }
$res = [ordered]@{ demo = $demoPath; t = $T; killer = $Killer; victim = $Victim; kid = $k; vid = $v; speed = $Speed; seek = $seek.Reported; lines = $lines.ToArray() }
$res | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Out -Encoding UTF8
"probe: $($lines.Count) lines, k=$k v=$v -> $Out"
