# Minimal obs-websocket v5 client (built-in OBS WebSocket server, localhost).
# Credentials are read from <toolkit>\runtime\obs-websocket.json (written by Setup.ps1) and never logged.
. (Join-Path $PSScriptRoot 'DDConfig.ps1')

$script:Ws = $null
$script:Events = New-Object System.Collections.Generic.List[object]
$script:SecretFile = Join-Path $DDRuntime 'obs-websocket.json'

# A receive is never cancelled (cancelling aborts a ClientWebSocket); a timed-out
# receive stays pending and is picked up by the next call.
$script:RxBuf = New-Object byte[] 1048576
$script:RxTask = $null
$script:RxStream = New-Object IO.MemoryStream

function Receive-OBSMessage {
    # Returns the next message, or $null after TimeoutMs.
    param([int]$TimeoutMs = 10000)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        if (-not $script:RxTask) {
            $seg = New-Object ArraySegment[byte] -ArgumentList (, $script:RxBuf)
            $script:RxTask = $script:Ws.ReceiveAsync($seg, [Threading.CancellationToken]::None)
        }
        $left = [int][math]::Max(0, $TimeoutMs - $sw.ElapsedMilliseconds)
        if (-not $script:RxTask.Wait($left)) { return $null }
        $r = $script:RxTask.Result
        $script:RxTask = $null
        if ($r.MessageType -eq 'Close') { throw 'OBS closed the WebSocket' }
        $script:RxStream.Write($script:RxBuf, 0, $r.Count)
        if ($r.EndOfMessage) {
            $txt = [Text.Encoding]::UTF8.GetString($script:RxStream.ToArray())
            $script:RxStream.SetLength(0)
            return ($txt | ConvertFrom-Json)
        }
    }
}

function Send-OBSMessage($Obj) {
    $json = $Obj | ConvertTo-Json -Depth 20 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $seg = New-Object ArraySegment[byte] -ArgumentList (, $bytes)
    [void]$script:Ws.SendAsync($seg, 'Text', $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
}

function Connect-OBS {
    param([double]$TimeoutSec = 30)
    $cfg = Get-Content $script:SecretFile -Raw | ConvertFrom-Json
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $script:RxTask = $null
    $script:RxStream.SetLength(0)
    while ($true) {
        try {
            $script:Ws = New-Object Net.WebSockets.ClientWebSocket
            [void]$script:Ws.ConnectAsync([Uri]"ws://$($cfg.host):$($cfg.port)", [Threading.CancellationToken]::None).GetAwaiter().GetResult()
            break
        } catch {
            if ($sw.Elapsed.TotalSeconds -gt $TimeoutSec) { throw "Cannot connect to OBS WebSocket: $($_.Exception.Message)" }
            Start-Sleep -Milliseconds 500
        }
    }
    $hello = Receive-OBSMessage
    $ident = @{ rpcVersion = 1; eventSubscriptions = 64 }   # 64 = Outputs (record state events)
    if ($hello.d.authentication) {
        $sha = [Security.Cryptography.SHA256]::Create()
        $secret = [Convert]::ToBase64String($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($cfg.password + $hello.d.authentication.salt)))
        $ident.authentication = [Convert]::ToBase64String($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($secret + $hello.d.authentication.challenge)))
    }
    Send-OBSMessage @{ op = 1; d = $ident }
    $m = Receive-OBSMessage
    if ($m.op -ne 2) { throw 'OBS WebSocket identification failed' }
    "Connected to OBS $($hello.d.obsWebSocketVersion) (rpc $($m.d.negotiatedRpcVersion))"
}

function Invoke-OBS {
    param([Parameter(Mandatory)][string]$Type, [hashtable]$Data = @{}, [switch]$AllowFail, [int]$TimeoutMs = 15000)
    if (-not $script:Ws -or $script:Ws.State -ne 'Open') { Connect-OBS | Out-Null }
    $id = [guid]::NewGuid().ToString()
    Send-OBSMessage @{ op = 6; d = @{ requestType = $Type; requestId = $id; requestData = $Data } }
    while ($true) {
        $m = Receive-OBSMessage -TimeoutMs $TimeoutMs
        if ($null -eq $m) { throw "OBS $Type timed out" }
        if ($m.op -eq 5) { $script:Events.Add($m.d); continue }
        if ($m.op -eq 7 -and $m.d.requestId -eq $id) {
            if (-not $m.d.requestStatus.result -and -not $AllowFail) {
                throw "OBS $Type failed: $($m.d.requestStatus.code) $($m.d.requestStatus.comment)"
            }
            return $m.d.responseData
        }
    }
}

function Wait-OBSEvent {
    param([Parameter(Mandatory)][string]$EventType, [scriptblock]$Where = { $true }, [double]$TimeoutSec = 30)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        foreach ($e in $script:Events.ToArray()) {
            if ($e.eventType -eq $EventType -and (& $Where $e.eventData)) { [void]$script:Events.Remove($e); return $e.eventData }
        }
        $m = Receive-OBSMessage -TimeoutMs 500
        if ($m -and $m.op -eq 5) { $script:Events.Add($m.d) }
    }
    throw "Timed out waiting for OBS event $EventType"
}

function Clear-OBSEvents { $script:Events.Clear() }

# OBS the toolkit started is recorded (PID + start time) in runtime\obs.pid. Recovery restarts only that one; an
# OBS the user opened themselves is reused for recording but never closed or killed.
$script:ObsPidFile = Join-Path $DDRuntime 'obs.pid'

function Get-OBSOwnedId {
    if (-not (Test-Path -LiteralPath $script:ObsPidFile)) { return -1 }
    $id, $start = (Get-Content -LiteralPath $script:ObsPidFile -Raw).Trim() -split '\s+', 2
    $p = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -eq 'obs64' -and $p.StartTime.ToString('o') -eq $start) { return [int]$id }
    return -1
}

function Start-OBSApp {
    if (Get-Process obs64 -ErrorAction SilentlyContinue) { return }
    $dir = $DDCfg.obsDir
    $obsArgs = @('--profile', 'UTVideo', '--collection', 'UTVideo', '--scene', 'UT99', '--disable-shutdown-check', '--disable-updater', '--minimize-to-tray')
    if ($DDCfg.obsPortable) { $obsArgs = @('--portable') + $obsArgs }   # settings in <OBS>\config, nothing in %APPDATA%
    $p = Start-Process "$dir\obs64.exe" -WorkingDirectory $dir -ArgumentList $obsArgs -PassThru
    Set-Content -LiteralPath $script:ObsPidFile "$($p.Id) $($p.StartTime.ToString('o'))" -Encoding Ascii
    # after an unclean exit OBS opens a "crash detected" dialog a few seconds later and waits; click it away
    for ($i = 0; $i -lt 12; $i++) { Start-Sleep -Milliseconds 750; Confirm-OBSCrashDialog }
}

# Mean brightness (0..255) of a small live screenshot of a source; ~0 = black capture.
function Get-OBSSourceLuma {
    param([string]$Source = 'UT Game')
    Add-Type -AssemblyName System.Drawing
    $sh = Invoke-OBS GetSourceScreenshot @{ sourceName = $Source; imageFormat = 'png'; imageWidth = 64; imageHeight = 36 }
    $bytes = [Convert]::FromBase64String(($sh.imageData -replace '^data:image/\w+;base64,', ''))
    $ms = New-Object IO.MemoryStream(, $bytes)
    $bmp = [Drawing.Bitmap]::FromStream($ms)
    $sum = 0.0
    for ($x = 0; $x -lt $bmp.Width; $x += 2) { for ($y = 0; $y -lt $bmp.Height; $y += 2) { $c = $bmp.GetPixel($x, $y); $sum += 0.299 * $c.R + 0.587 * $c.G + 0.114 * $c.B } }
    $n = [math]::Ceiling($bmp.Width / 2) * [math]::Ceiling($bmp.Height / 2)
    $bmp.Dispose(); $ms.Dispose()
    return $sum / $n
}

# Click through OBS's "crash detected" dialog (shown after an unclean exit) -> normal mode.
function Confirm-OBSCrashDialog {
    Add-Type -AssemblyName UIAutomationClient
    $p = Get-Process obs64 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $p) { return }
    $cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
    $w = [Windows.Automation.AutomationElement]::RootElement.FindFirst('Children', $cond)
    if (-not $w) { return }
    $btnType = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::Button)
    foreach ($b in $w.FindAll('Descendants', $btnType)) {
        if ($b.Current.Name -match '(?i)normal') { $b.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke(); return }
    }
}

# Restart OBS (stale game-capture hooks after many game restarts record black frames).
function Restart-OBSApp {
    # another job may be recording with this OBS: only the holder of the job lock (UTDirector) may restart it
    if (Get-Command Enter-DDJob -ErrorAction SilentlyContinue) { Enter-DDJob }
    $all = @(Get-Process obs64 -ErrorAction SilentlyContinue)
    $own = Get-OBSOwnedId
    $foreign = @($all | Where-Object Id -ne $own)
    if ($foreign) {
        throw "OBS (PID $($foreign.Id -join ', ')) was not started by the toolkit, so it is not restarted automatically. " +
              'Its capture went stale (black frames): restart OBS yourself, then run again.'
    }
    $p = $all | Where-Object Id -eq $own
    if ($p) {
        [void]$p.CloseMainWindow()
        if (-not $p.WaitForExit(15000)) { $p.Kill(); $p.WaitForExit(5000) | Out-Null; Start-Sleep 2 }
    }
    $script:Ws = $null
    Start-OBSApp
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep 1
        Confirm-OBSCrashDialog
        try { Connect-OBS -TimeoutSec 2 | Out-Null; return } catch {}
    }
    Connect-OBS -TimeoutSec 30 | Out-Null
}

Export-ModuleMember -Function Connect-OBS, Invoke-OBS, Wait-OBSEvent, Clear-OBSEvents, Start-OBSApp, Get-OBSSourceLuma, Confirm-OBSCrashDialog, Restart-OBSApp
