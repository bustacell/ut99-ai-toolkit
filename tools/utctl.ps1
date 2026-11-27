# UT99 control helper: writes console commands to runtime\cmd.txt and triggers them
# via the ScrollLock binding ("exec <toolkit>\runtime\cmd.txt") in User.ini.
param(
    [Parameter(Mandatory)][string[]]$Commands,
    [int]$WaitMs = 600
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DDConfig.ps1')
$cmdFile = Join-Path $DDRuntime 'cmd.txt'
Set-Content $cmdFile ($Commands -join "`r`n") -Encoding Ascii

if (-not ('UTWin' -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class UTWin {
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint c, uint t);
    public static void Key(IntPtr h, uint vk) {
        uint sc = MapVirtualKey(vk, 0);
        PostMessage(h, 0x0100, (IntPtr)vk, (IntPtr)(1 | (sc << 16)));
        System.Threading.Thread.Sleep(40);
        PostMessage(h, 0x0101, (IntPtr)vk, (IntPtr)(1 | (sc << 16) | (1u << 30) | (1u << 31)));
    }
}
'@
}
$p = Get-Process UnrealTournament -ErrorAction SilentlyContinue | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1
if (-not $p) { throw 'UnrealTournament window not found' }
[UTWin]::Key($p.MainWindowHandle, 0x91)   # VK_SCROLL
Start-Sleep -Milliseconds $WaitMs
