# Mouse/keyboard helpers for driving UnrealEd (no API for its UI). Dot-source, then: Focus-Ued; Move-To x y;
# Drag-Mouse x0 y0 x1 y1 [button] [ms]; Wheel x y clicks; Press-Keys "{ENTER}"; Save-Screen path
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class UIn {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, int data, IntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@
$script:BTN = @{ left = @(0x2, 0x4); right = @(0x8, 0x10); middle = @(0x20, 0x40) }
function Focus-Ued { $p = Get-Process UnrealEd -ErrorAction Stop | Select-Object -First 1; [void][UIn]::ShowWindow($p.MainWindowHandle, 3); [void][UIn]::SetForegroundWindow($p.MainWindowHandle); Start-Sleep -Milliseconds 300 }
function Move-To([int]$x, [int]$y) { [void][UIn]::SetCursorPos($x, $y) }
function Click-At([int]$x, [int]$y, [string]$button = 'left') {
    Move-To $x $y; Start-Sleep -Milliseconds 60
    [UIn]::mouse_event($script:BTN[$button][0], 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 40
    [UIn]::mouse_event($script:BTN[$button][1], 0, 0, 0, [IntPtr]::Zero)
}
function Drag-Mouse([int]$x0, [int]$y0, [int]$x1, [int]$y1, [string]$button = 'left', [int]$ms = 1500) {
    # smooth drag in small steps (UnrealEd reads relative mouse motion while a button is held)
    Move-To $x0 $y0; Start-Sleep -Milliseconds 80
    [UIn]::mouse_event($script:BTN[$button][0], 0, 0, 0, [IntPtr]::Zero)
    $n = [math]::Max(1, [int]($ms / 16))
    for ($i = 1; $i -le $n; $i++) {
        Move-To ([int]($x0 + ($x1 - $x0) * $i / $n)) ([int]($y0 + ($y1 - $y0) * $i / $n)); Start-Sleep -Milliseconds 16
    }
    [UIn]::mouse_event($script:BTN[$button][1], 0, 0, 0, [IntPtr]::Zero)
}
function Drag-Rel([int]$x0, [int]$y0, [int]$dx, [int]$dy, [string]$button = 'left', [int]$ms = 1500) {
    # relative motion (MOUSEEVENTF_MOVE) while the button is held: UnrealEd viewports read raw mouse deltas
    Move-To $x0 $y0; Start-Sleep -Milliseconds 80
    [UIn]::mouse_event($script:BTN[$button][0], 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 30
    $n = [math]::Max(1, [int]($ms / 16)); $sx = 0; $sy = 0
    for ($i = 1; $i -le $n; $i++) {
        $tx = [int]($dx * $i / $n); $ty = [int]($dy * $i / $n)
        [UIn]::mouse_event(0x1, $tx - $sx, $ty - $sy, 0, [IntPtr]::Zero); $sx = $tx; $sy = $ty
        Start-Sleep -Milliseconds 16
    }
    [UIn]::mouse_event($script:BTN[$button][1], 0, 0, 0, [IntPtr]::Zero)
}
function Wheel([int]$x, [int]$y, [int]$clicks) {
    Move-To $x $y; Start-Sleep -Milliseconds 50
    for ($i = 0; $i -lt [math]::Abs($clicks); $i++) {
        [UIn]::mouse_event(0x800, 0, 0, [math]::Sign($clicks) * 120, [IntPtr]::Zero); Start-Sleep -Milliseconds 40
    }
}
function Press-Keys([string]$keys) { [System.Windows.Forms.SendKeys]::SendWait($keys); Start-Sleep -Milliseconds 150 }
function Save-Screen([string]$path) {
    $bmp = New-Object Drawing.Bitmap 1920, 1080; $g = [Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save($path); $g.Dispose(); $bmp.Dispose()
}
