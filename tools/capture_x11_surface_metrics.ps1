<#
.SYNOPSIS
    Capture host-side evidence for a Termux:X11 native-wide surface probe.

.DESCRIPTION
    Writes Android display/window metrics, Termux:X11 activity metrics, a
    screenshot, and optional Termux-side X display facts into a local run
    directory. Real run output belongs under runs/ and should not be committed.
#>
[CmdletBinding()]
param(
    [string]$Adb = 'adb',
    [string]$Serial = '',
    [string]$OutDir = '',
    [string]$Package = 'com.termux.x11',
    [string]$TermuxPackage = 'com.termux',
    [switch]$SkipScreenshot,
    [switch]$SkipTermuxDisplay
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $OutDir) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $OutDir = Join-Path (Join-Path (Get-Location) 'runs') "x11-wide-$stamp"
}
$OutDir = (New-Item -ItemType Directory -Force -Path $OutDir).FullName

function Get-AdbPrefix {
    if ($Serial) {
        return @('-s', $Serial)
    }
    return @()
}

function Invoke-AdbText {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFail
    )

    $path = Join-Path $OutDir "$Name.txt"
    $fullArgs = @()
    $fullArgs += Get-AdbPrefix
    $fullArgs += $Arguments
    $commandLine = "$Adb $($fullArgs -join ' ')"
    Set-Content -LiteralPath (Join-Path $OutDir "$Name.command.txt") -Encoding UTF8 -Value $commandLine

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & $Adb @fullArgs 2>&1 | Out-String
    $exitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    $ErrorActionPreference = $oldPreference

    Set-Content -LiteralPath $path -Encoding UTF8 -Value $output
    if ($exitCode -ne 0 -and -not $AllowFail) {
        throw "ADB command failed with exit code $exitCode`: $Name"
    }
    return $path
}

function Invoke-AdbPullScreenshot {
    if ($SkipScreenshot) {
        return $null
    }

    $remote = '/sdcard/termux_x11_native_wide.png'
    $local = Join-Path $OutDir 'termux_x11_native_wide.png'
    Invoke-AdbText -Name 'screencap-device' -Arguments @('shell', "screencap -p $remote") -AllowFail | Out-Null
    Invoke-AdbText -Name 'screencap-pull' -Arguments @('pull', $remote, $local) -AllowFail | Out-Null
    Invoke-AdbText -Name 'screencap-cleanup' -Arguments @('shell', "rm -f $remote") -AllowFail | Out-Null
    return $local
}

$artifacts = [ordered]@{}
$artifacts['wm_size'] = Invoke-AdbText -Name 'wm_size' -Arguments @('shell', 'wm size') -AllowFail
$artifacts['wm_density'] = Invoke-AdbText -Name 'wm_density' -Arguments @('shell', 'wm density') -AllowFail
$artifacts['activity_top'] = Invoke-AdbText -Name 'activity_top' -Arguments @('shell', 'dumpsys activity top') -AllowFail
$artifacts['window'] = Invoke-AdbText -Name 'window' -Arguments @('shell', 'dumpsys window') -AllowFail
$artifacts['surfaceflinger'] = Invoke-AdbText -Name 'surfaceflinger' -Arguments @('shell', 'dumpsys SurfaceFlinger') -AllowFail
$artifacts['gfxinfo'] = Invoke-AdbText -Name 'gfxinfo_termux_x11' -Arguments @('shell', "dumpsys gfxinfo $Package") -AllowFail
$screenshot = Invoke-AdbPullScreenshot
if ($screenshot) {
    $artifacts['screenshot'] = $screenshot
}

if (-not $SkipTermuxDisplay) {
    $termuxPrelude = 'export HOME=/data/data/com.termux/files/home; export PREFIX=/data/data/com.termux/files/usr; export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; export DISPLAY=:1;'
    $artifacts['termux_xdpyinfo'] = Invoke-AdbText -Name 'termux_xdpyinfo' -Arguments @('shell', "run-as $TermuxPackage /data/data/com.termux/files/usr/bin/sh -lc '$termuxPrelude xdpyinfo 2>&1 || true'") -AllowFail
    $artifacts['termux_xrandr'] = Invoke-AdbText -Name 'termux_xrandr' -Arguments @('shell', "run-as $TermuxPackage /data/data/com.termux/files/usr/bin/sh -lc '$termuxPrelude xrandr 2>&1 || true'") -AllowFail
    $artifacts['termux_glxinfo_B'] = Invoke-AdbText -Name 'termux_glxinfo_B' -Arguments @('shell', "run-as $TermuxPackage /data/data/com.termux/files/usr/bin/sh -lc '$termuxPrelude glxinfo -B 2>&1 || true'") -AllowFail
}

$manifest = [ordered]@{
    schema = 'quest-termux-lab.x11-surface-capture-manifest.v1'
    captured_at = (Get-Date).ToUniversalTime().ToString('o')
    package = $Package
    out_dir = $OutDir
    artifacts = $artifacts
}
$manifestPath = Join-Path $OutDir 'capture_manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "capture_manifest=$manifestPath"
