# UTDirector.psm1 - control UT99 (OldUnreal 469f + uDemo + DemoDirector helper package)
# Channel in:  ScrollLock is bound in User.ini to "exec <toolkit>\runtime\cmd.txt" (done by Setup.ps1);
#              we write commands into that file and post a ScrollLock key to the UT window
#              (PostMessage, so the window does not need focus).
# Channel out: DemoDirector.DDConsole writes "DemoDirector: DD|TAG|t=<demo s>|k=v|..." lines
#              into System\UnrealTournament.log (game is started with -FORCELOGFLUSH).

. (Join-Path $PSScriptRoot 'DDConfig.ps1')
$script:UTRoot   = $DDUT
$script:UTSystem = Join-Path $UTRoot 'System'
$script:UTLog    = Join-Path $UTSystem 'UnrealTournament.log'
$script:Runtime  = $DDRuntime
$script:CmdFile  = Join-Path $Runtime 'cmd.txt'
$script:LogPos   = 0

if (-not ('UTWin' -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class UTWin {
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint c, uint t);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public static void Key(IntPtr h, uint vk) {
        uint sc = MapVirtualKey(vk, 0);
        PostMessage(h, 0x0100, (IntPtr)vk, (IntPtr)(1 | (sc << 16)));
        System.Threading.Thread.Sleep(40);
        PostMessage(h, 0x0101, (IntPtr)vk, (IntPtr)(1 | (sc << 16) | (1u << 30) | (1u << 31)));
    }
}
'@
}
Add-Type -AssemblyName UIAutomationClient

if (-not ('UTPower' -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class UTPower {
    [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
}
'@
}
# Ask Windows to keep the display on and not sleep while we record (temporary request, like a
# video player; no power settings are changed). Display-off made OBS record black frames.
function Set-UTKeepAwake {
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED (also resets the idle timers)
    [void][UTPower]::SetThreadExecutionState([uint32]2147483651)
}

# --- process ownership -------------------------------------------------------------------------------
# The toolkit only ever touches the UT of the configured install (config utRoot), and only closes or kills a UT it
# started itself (PID recorded in runtime\ut.pid). A UT the user opened is left alone: the tools stop with a clear
# message instead. Scripts that launch UT with Start-Process themselves call Register-UTProcess.
$script:UTExe = Join-Path $script:UTSystem 'UnrealTournament.exe'
$script:UTPidFile = Join-Path $script:Runtime 'ut.pid'

function Get-UTProcess {
    $want = [IO.Path]::GetFullPath($script:UTExe)
    $own = Get-UTOwnedId
    Get-Process UnrealTournament -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -eq $own -or $(try { $_.Path -and [IO.Path]::GetFullPath($_.Path) -eq $want } catch { $false })
    } | Select-Object -First 1
}

function Get-UTOwnedId {
    # PID + start time, so a recycled PID after a reboot never counts as ours
    if (-not (Test-Path -LiteralPath $script:UTPidFile)) { return -1 }
    $id, $start = (Get-Content -LiteralPath $script:UTPidFile -Raw).Trim() -split '\s+', 2
    $p = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
    if ($p -and $p.StartTime.ToString('o') -eq $start) { return [int]$id }
    return -1
}

function Register-UTProcess([Parameter(Mandatory)][Diagnostics.Process]$Process) {
    Enter-DDJob                  # whoever starts the game owns it for this job
    Set-Content -LiteralPath $script:UTPidFile "$($Process.Id) $($Process.StartTime.ToString('o'))" -Encoding Ascii
}

function Test-UTOwned([Diagnostics.Process]$Process) { $Process -and $Process.Id -eq (Get-UTOwnedId) }

# --- one job at a time -----------------------------------------------------------------------------------
# All tools share runtime\cmd.txt and the game window, so two jobs at once would steer each other's game. The
# first command a job sends takes runtime\job.lock (an open file handle: Windows releases it when the process
# ends, even after a crash). A second job fails fast and names the holder. Exit-DDJob releases it early.
function Enter-DDJob {
    if ($global:DDJobLock -and $global:DDJobLock.CanWrite) { return }
    New-Item -ItemType Directory -Force $script:Runtime | Out-Null
    $f = Join-Path $script:Runtime 'job.lock'
    try { $s = [IO.File]::Open($f, 'OpenOrCreate', 'ReadWrite', 'Read') }
    catch {
        $who = try { (Get-Content -LiteralPath $f -Raw).Trim() } catch { 'unknown' }
        throw "Another toolkit job is using the game right now ($who). Wait for it to finish, or stop it first."
    }
    $s.SetLength(0)
    $top = (Get-PSCallStack | Where-Object ScriptName | Select-Object -Last 1).ScriptName
    $b = [Text.Encoding]::UTF8.GetBytes("pid $PID since $(Get-Date -Format s), $(if ($top) { [IO.Path]::GetFileName($top) } else { 'interactive' })")
    $s.Write($b, 0, $b.Length); $s.Flush()
    $global:DDJobLock = $s
}

function Exit-DDJob {
    if ($global:DDJobLock) { $global:DDJobLock.Dispose(); $global:DDJobLock = $null }
}

function Read-UTLogNew {
    # Returns log lines appended since the last call (shared read, game keeps file open).
    if (-not (Test-Path $UTLog)) { return @() }
    $fs = [IO.File]::Open($UTLog, 'Open', 'Read', 'ReadWrite')
    try {
        if ($fs.Length -lt $script:LogPos) { $script:LogPos = 0 }
        $fs.Position = $script:LogPos
        $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::Default)
        $txt = $sr.ReadToEnd()
        $script:LogPos = $fs.Position
    } finally { $fs.Dispose() }
    if (-not $txt) { return @() }
    return $txt -split "`r?`n" | Where-Object { $_ -ne '' }
}

function Reset-UTLogCursor {
    if (Test-Path $UTLog) { $script:LogPos = (Get-Item $UTLog).Length } else { $script:LogPos = 0 }
}

function ConvertFrom-DDLine([string]$Line) {
    # "DemoDirector: DD|STATE|t=1.2|total=536|view=x" -> object
    if ($Line -notmatch '^DemoDirector: DD\|([A-Z_]+)\|(.*)$') { return $null }
    $o = [ordered]@{ Tag = $Matches[1]; Raw = $Line }
    $rest = $Matches[2]
    $parts = $rest -split '\|'
    $free = @()
    foreach ($p in $parts) {
        if ($p -match '^([a-z]+)=(.*)$') { $o[$Matches[1]] = $Matches[2] } else { $free += $p }
    }
    $o['Text'] = ($free -join '|')
    if ($o.Contains('t')) { $o['t'] = [double]$o['t'] }
    return [pscustomobject]$o
}

function Wait-UTLog {
    # Wait until a new log line matches $Pattern. Returns the line (or $null on timeout).
    param([Parameter(Mandatory)][string]$Pattern, [double]$TimeoutSec = 30, [switch]$All)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $acc = @()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        foreach ($l in (Read-UTLogNew)) {
            $acc += $l
            if ($l -match '^Critical:') { throw "UT crashed: $l" }
            if ($l -match $Pattern) { if ($All) { return $acc } else { return $l } }
        }
        if (-not (Get-UTProcess)) { throw 'UT process exited' }
        Start-Sleep -Milliseconds 100
    }
    return $null
}

function Send-UTCommand {
    # Execute one or more console commands inside UT.
    param([Parameter(Mandatory)][string[]]$Commands, [int]$SettleMs = 150)
    foreach ($c in $Commands) { if ($c -match '[\r\n]') { throw "Invalid command: $c" } }
    Enter-DDJob
    $p = Get-UTProcess
    if (-not $p -or $p.MainWindowHandle -eq 0) { throw 'UnrealTournament window not found' }
    Set-Content $CmdFile ($Commands -join "`r`n") -Encoding Ascii
    [UTWin]::Key($p.MainWindowHandle, 0x91)   # VK_SCROLL -> exec cmd.txt
    Start-Sleep -Milliseconds $SettleMs
}

function Get-UTStatus {
    param([double]$TimeoutSec = 5)
    Send-UTCommand 'ddstatus' -SettleMs 0
    $l = Wait-UTLog -Pattern '^DemoDirector: DD\|STATUS\|' -TimeoutSec $TimeoutSec
    if ($l) { return ConvertFrom-DDLine $l }
    return $null
}

function Get-UTPlayers {
    Send-UTCommand 'ddplayers' -SettleMs 0
    $lines = Wait-UTLog -Pattern 'DD\|PLAYERS_END' -TimeoutSec 5 -All
    $lines | ForEach-Object { ConvertFrom-DDLine $_ } | Where-Object { $_ -and $_.Tag -eq 'PLAYER' }
}

function Invoke-UTRecoveryDialog {
    # 469 shows a "Recovery Mode" wizard after an unclean shutdown; click "Run Unreal Tournament".
    param($Process)
    $cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty, $Process.Id)
    $w = [Windows.Automation.AutomationElement]::RootElement.FindFirst('Children', $cond)
    if (-not $w) { return $false }
    $nc = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, 'Run Unreal Tournament')
    $b = $w.FindFirst('Descendants', $nc)
    if (-not $b) { return $false }
    $b.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    return $true
}

function Sync-UTBinding {
    # The ScrollLock binding holds an absolute path to runtime\cmd.txt. On a portable drive the letter can
    # change, so re-point it (only that one line, only when it differs; Setup.ps1 made the backup).
    $userIni = Join-Path $UTSystem 'User.ini'
    if (-not (Test-Path $userIni)) { return }
    $want = "ScrollLock=exec $CmdFile"
    $lines = Get-Content -LiteralPath $userIni
    $i = [array]::FindIndex([string[]]$lines, [Predicate[string]] { param($l) $l -like 'ScrollLock=*' })
    if ($i -ge 0 -and $lines[$i] -ne $want) { $lines[$i] = $want; Set-Content -LiteralPath $userIni $lines -Encoding Ascii }
}

function Start-UTDemo {
    # Launch UT and play a demo. Returns when the DemoDirector watcher reports the demo level.
    param([Parameter(Mandatory)][string]$DemoPath, [double]$TimeoutSec = 90)
    $full = Resolve-DDDemo $DemoPath   # moved archives are found by file name; clear error if a demo drive is unplugged
    if ($full -notmatch '\.dem$') { throw "Not a .dem file: $full" }
    Enter-DDJob
    if (Get-UTProcess) { Stop-UT }
    Sync-UTBinding
    # demoplay path relative to System so UT finds it regardless of DemoPaths
    $rel = [IO.Path]::GetRelativePath($UTSystem, $full)
    if ($rel -match '\s') { throw "Demo path must not contain spaces: $rel" }
    # ddautoclose: some demos open a window by themselves (server rules browser) that swallows the command key
    Set-Content (Join-Path $Runtime 'start.txt') "ddautoclose 1`r`ndemoplay $rel" -Encoding Ascii
    $script:LogPos = 0
    # $env:UT_MINIMIZED = '1': start minimized and keep it minimized without focus (scans only, nothing is recorded;
    # the user can keep working). Rendering needs the visible window (OBS captures it).
    $min = $env:UT_MINIMIZED -eq '1'
    $sp = @{ FilePath = (Join-Path $UTSystem 'UnrealTournament.exe'); ArgumentList = "-exec=$(Join-Path $Runtime 'start.txt')", '-FORCELOGFLUSH'
             WorkingDirectory = $UTSystem; PassThru = $true }
    if ($min) { $sp.WindowStyle = 'Minimized' }
    $prevFg = [UTWin]::GetForegroundWindow()   # the user's window, handed back after UT grabs focus
    $p = Start-Process @sp
    Register-UTProcess $p
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Sleep 2
    $script:LogPos = 0
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        $p.Refresh()
        if ($p.HasExited) { throw 'UT exited during startup' }
        if ($p.MainWindowTitle -like '*Recovery Mode*') { [void](Invoke-UTRecoveryDialog $p); Start-Sleep 2; continue }
        if ($min -and $p.MainWindowHandle -ne 0) {
            [void][UTWin]::ShowWindow($p.MainWindowHandle, 7)   # SW_SHOWMINNOACTIVE
            if ($prevFg -ne [IntPtr]::Zero -and [UTWin]::GetForegroundWindow() -eq $p.MainWindowHandle) { [void][UTWin]::SetForegroundWindow($prevFg) }
        }
        foreach ($l in (Read-UTLogNew)) {
            if ($l -match '^Critical:') { throw "UT crashed: $l" }
            if ($l -match 'DD\|WATCHER\|') {
                # time-based playback: demo time advances 1:1 with real time (x slomo).
                # (frame-based mode plays one demo frame per rendered frame = wrong speed)
                Start-Sleep -Milliseconds 500
                Send-UTCommand 'ddautoclose 1', 'playback 0' -SettleMs 200
                return (ConvertFrom-DDLine $l)
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Demo did not start within $TimeoutSec s"
}

function Invoke-UTSeek {
    # Seek to demo time (seconds since demo start, uDemo SeekTo). Returns the reported time after the seek.
    param([Parameter(Mandatory)][double]$Seconds, [double]$TimeoutSec = 240)
    if ($env:DD_SEEK_TIMEOUT) { $TimeoutSec = [double]$env:DD_SEEK_TIMEOUT }   # heavy late seeks (20+ min demos)
    $st = Get-UTStatus
    # Long forward jumps: uDemo's SeekTo can be very slow on heavy demos, so fast-forward
    # at 32x (as fast as the scanner) to just before the target, then finish with SeekTo.
    # Stop 30 s short: on crowded demos (20 players) status polling lags and 32x overshot by 13-18 s, and every
    # retry is then a slow backward seek. SeekTo covers the last 30 s forward.
    if ($st -and ($Seconds - $st.t) -gt 45) {
        if ($st.paused -ne '0') { Send-UTCommand 'pause' -SettleMs 100 }
        Send-UTCommand 'slomo 32' -SettleMs 0
        try {
            $ff = [Diagnostics.Stopwatch]::StartNew()
            while ($ff.Elapsed.TotalSeconds -lt $TimeoutSec) {
                Start-Sleep -Milliseconds 250
                $cur = Get-UTStatus
                if ($cur -and $cur.t -ge $Seconds - 30) { break }
            }
        } finally {
            # slomo is saved to the ini (GameSpeed); never leave it at 32, also when the caller is interrupted
            Send-UTCommand 'slomo 1' -SettleMs 100
        }
    }
    Send-UTCommand ("seekto {0}" -f $Seconds.ToString([Globalization.CultureInfo]::InvariantCulture)) -SettleMs 0
    $sw = [Diagnostics.Stopwatch]::StartNew()
    # uDemo logs "<lts> EndSeek at <t>" when it is done
    $l = Wait-UTLog -Pattern 'EndSeek at' -TimeoutSec $TimeoutSec
    if (-not $l) { throw "Seek to $Seconds did not finish within $TimeoutSec s" }
    Start-Sleep -Milliseconds 300
    $after = Get-UTStatus
    [pscustomobject]@{ Requested = $Seconds; Reported = $after.t; WallSec = [math]::Round($sw.Elapsed.TotalSeconds, 2); EndSeekLine = $l }
}

function Stop-UT {
    # Close the toolkit's UT: politely ('exit'), then kill. -Force kills at once (recovery after a hang).
    # A UT the toolkit did not start is never touched: that throws, so the user can close their own game.
    param([switch]$Force)
    $p = Get-UTProcess
    if (-not $p) { return }
    if (-not (Test-UTOwned $p)) {
        throw "UnrealTournament (PID $($p.Id)) is running but was not started by the toolkit. Close it yourself, then run again."
    }
    # The toolkit's UT may belong to ANOTHER job that is still running: only the holder of the job lock may close it.
    # Enter-DDJob throws (naming the holder) before anything is touched; for the job itself it is a no-op.
    Enter-DDJob
    if (-not $Force) { try { Send-UTCommand 'exit' -SettleMs 0 } catch {} }   # window gone etc.: kill below
    if ($Force -or -not $p.WaitForExit(10000)) { $p.Kill(); $p.WaitForExit(5000) | Out-Null }
    Remove-Item -LiteralPath $script:UTPidFile -ErrorAction SilentlyContinue
}

Export-ModuleMember -Function *-UT*, Read-UTLogNew, Reset-UTLogCursor, ConvertFrom-DDLine, Register-UTProcess, Test-UTOwned,
    Enter-DDJob, Exit-DDJob
