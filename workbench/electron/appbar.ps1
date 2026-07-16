param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('reserve', 'remove')]
  [string]$Action,
  [Parameter(Mandatory = $true)]
  [long]$Hwnd,
  [int]$Left = 0,
  [int]$Top = 0,
  [int]$Right = 0,
  [int]$Bottom = 0,
  [int]$Width = 420,
  [int]$Register = 0
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$source = @'
using System;
using System.Runtime.InteropServices;

public static class AetherAppBarNative
{
    public const uint ABM_NEW = 0x00000000;
    public const uint ABM_REMOVE = 0x00000001;
    public const uint ABM_QUERYPOS = 0x00000002;
    public const uint ABM_SETPOS = 0x00000003;
    public const uint ABE_LEFT = 0;

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int left;
        public int top;
        public int right;
        public int bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct APPBARDATA
    {
        public uint cbSize;
        public IntPtr hWnd;
        public uint uCallbackMessage;
        public uint uEdge;
        public RECT rc;
        public IntPtr lParam;
    }

    [DllImport("shell32.dll", CallingConvention = CallingConvention.StdCall)]
    public static extern UIntPtr SHAppBarMessage(uint dwMessage, ref APPBARDATA data);
}
'@

$null = Add-Type -TypeDefinition $source -Language CSharp
$data = New-Object AetherAppBarNative+APPBARDATA
$data.cbSize = [Runtime.InteropServices.Marshal]::SizeOf([type][AetherAppBarNative+APPBARDATA])
$data.hWnd = [IntPtr]::new($Hwnd)
$data.uCallbackMessage = 0x8001
$data.uEdge = [AetherAppBarNative]::ABE_LEFT

if ($Action -eq 'remove') {
  $null = [AetherAppBarNative]::SHAppBarMessage([AetherAppBarNative]::ABM_REMOVE, [ref]$data)
  @{ removed = $true } | ConvertTo-Json -Compress
  exit 0
}

if ($Register -eq 1) {
  $null = [AetherAppBarNative]::SHAppBarMessage([AetherAppBarNative]::ABM_NEW, [ref]$data)
}

$rect = New-Object AetherAppBarNative+RECT
$rect.left = $Left
$rect.top = $Top
$rect.right = $Right
$rect.bottom = $Bottom
$data.rc = $rect
$null = [AetherAppBarNative]::SHAppBarMessage([AetherAppBarNative]::ABM_QUERYPOS, [ref]$data)
$rect = $data.rc
$rect.right = $rect.left + $Width
$data.rc = $rect
$null = [AetherAppBarNative]::SHAppBarMessage([AetherAppBarNative]::ABM_SETPOS, [ref]$data)

@{
  x = $data.rc.left
  y = $data.rc.top
  width = $data.rc.right - $data.rc.left
  height = $data.rc.bottom - $data.rc.top
} | ConvertTo-Json -Compress
