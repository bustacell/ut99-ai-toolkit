<#
.SYNOPSIS
  Helpers for the terminal of the making-of run: type text like a person, press keys, take a screenshot.
  Dot-source it:  . .\TermKeys.ps1
#>
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
if (-not ('DDTerm.Win' -as [type])) {
    Add-Type -Namespace DDTerm -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(System.IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(System.IntPtr h, System.Text.StringBuilder s, int n);
'@
}

function Get-TermForeground {
    $h = [DDTerm.Win]::GetForegroundWindow()
    $t = [Text.StringBuilder]::new(256); $c = [Text.StringBuilder]::new(256)
    [void][DDTerm.Win]::GetWindowText($h, $t, 256); [void][DDTerm.Win]::GetClassName($h, $c, 256)
    [pscustomobject]@{ Handle = $h; Title = $t.ToString(); Class = $c.ToString() }
}

function Assert-TermFocus {
    # Keys go to whatever has focus, so refuse to type unless Windows Terminal is in front.
    $f = Get-TermForeground
    if ($f.Class -ne 'CASCADIA_HOSTING_WINDOW_CLASS') { throw "Windows Terminal is not in front (foreground: '$($f.Title)' / $($f.Class)). Nothing typed." }
}

function Send-TermText([string]$Text, [int]$DelayMs = 95) {
    Assert-TermFocus
    foreach ($ch in $Text.ToCharArray()) {
        $k = if ('+^%~(){}[]'.Contains($ch)) { "{$ch}" } else { [string]$ch }
        [Windows.Forms.SendKeys]::SendWait($k)
        Start-Sleep -Milliseconds ($DelayMs + (Get-Random -Minimum -25 -Maximum 45))
    }
}

function Send-TermKey([string]$Keys) {
    # SendKeys notation: {ENTER} {ESC} {UP} {DOWN} {TAB} ^= (Ctrl and =) ...
    Assert-TermFocus
    [Windows.Forms.SendKeys]::SendWait($Keys)
}

function Save-Screen([string]$Path, [double]$Scale = 1.0) {
    $b = [Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = [Drawing.Bitmap]::new($b.Width, $b.Height)
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [Drawing.Point]::Empty, $b.Size)
    $g.Dispose()
    if ($Scale -ne 1.0) {
        $s = [Drawing.Bitmap]::new([int]($b.Width * $Scale), [int]($b.Height * $Scale))
        $g2 = [Drawing.Graphics]::FromImage($s); $g2.InterpolationMode = 'HighQualityBicubic'
        $g2.DrawImage($bmp, 0, 0, $s.Width, $s.Height); $g2.Dispose(); $bmp.Dispose(); $bmp = $s
    }
    $bmp.Save($Path, [Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}
