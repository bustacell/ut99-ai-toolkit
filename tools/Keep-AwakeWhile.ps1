# Keeps Windows from idle sleep while a process with the given name runs (temporary request, like a video player;
# no power settings are changed). Ends by itself when the last such process has exited.
#   Start-Process pwsh -WindowStyle Hidden -ArgumentList '-File', 'Keep-AwakeWhile.ps1', 'blender'
param([string]$Name = 'blender', [int]$GraceSeconds = 120)
Add-Type -Namespace KA -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$idle = 0
while ($idle -lt $GraceSeconds) {
    if (Get-Process $Name -ErrorAction SilentlyContinue) { $idle = 0 } else { $idle += 30 }
    [void][KA.P]::SetThreadExecutionState([uint32]2147483649)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    Start-Sleep -Seconds 30
}
[void][KA.P]::SetThreadExecutionState([uint32]2147483648)       # ES_CONTINUOUS: release
