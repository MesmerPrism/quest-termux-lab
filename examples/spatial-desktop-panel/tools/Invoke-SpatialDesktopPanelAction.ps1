[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9._:-]+$')]
  [string]$Serial,

  [ValidateSet('window', 'spatial')]
  [string]$Presentation = 'window',

  [Parameter(Mandatory = $true)]
  [ValidateSet('connect', 'disconnect', 'size-up', 'size-down', 'recenter-panel', 'switch-presentation', 'right-click', 'scroll-up', 'scroll-down', 'camera-50', 'camera-51', 'microphone-toggle', 'show-keyboard', 'pointer-move', 'pointer-down', 'pointer-up', 'tap', 'drag', 'type-text', 'enter', 'start-sidecar', 'start-witness', 'stop-witness')]
  [string]$Action,

  [ValidateRange(0, 4095)]
  [int]$X,

  [ValidateRange(0, 4095)]
  [int]$Y,

  [ValidateRange(0, 4095)]
  [int]$X2,

  [ValidateRange(0, 4095)]
  [int]$Y2,

  [ValidateLength(1, 128)]
  [string]$Text,

  [ValidateRange(1, 60)]
  [int]$TimeoutSeconds = 20,

  [string]$EvidenceDirectory
)

$ErrorActionPreference = 'Stop'
$package = 'io.github.mesmerprism.questtermuxlab.spatialdesktop'
$activity = if ($Presentation -eq 'spatial') { "$package/.SpatialDesktopActivity" } else { "$package/.DesktopPanelActivity" }
$intentAction = "$package.DEBUG_PANEL_ACTION"
$coordinateActions = @('pointer-move', 'pointer-down', 'pointer-up', 'tap')
$dragCoordinateNames = @('X', 'Y', 'X2', 'Y2')

if ($Action -eq 'drag') {
  foreach ($name in $dragCoordinateNames) {
    if (-not $PSBoundParameters.ContainsKey($name)) { throw "Action 'drag' requires -X, -Y, -X2 and -Y2." }
  }
} elseif ($coordinateActions -contains $Action) {
  if (-not $PSBoundParameters.ContainsKey('X') -or -not $PSBoundParameters.ContainsKey('Y')) {
    throw "Action '$Action' requires -X and -Y."
  }
} elseif ($dragCoordinateNames | Where-Object { $PSBoundParameters.ContainsKey($_) }) {
  throw "-X, -Y, -X2 and -Y2 are accepted only for pointer actions."
}

if ($Action -ne 'drag' -and ($PSBoundParameters.ContainsKey('X2') -or $PSBoundParameters.ContainsKey('Y2'))) {
  throw '-X2 and -Y2 are accepted only for drag.'
}

if ($Action -eq 'type-text') {
  if (-not $PSBoundParameters.ContainsKey('Text')) { throw "Action 'type-text' requires -Text." }
  if ($Text -notmatch '^[\x20-\x7E]+$') { throw '-Text accepts printable ASCII only.' }
} elseif ($PSBoundParameters.ContainsKey('Text')) {
  throw '-Text is accepted only for type-text.'
}

$requestId = "cli-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())-$PID"
$adbArgs = @(
  '-s', $Serial, 'shell', 'am', 'start', '-W', '-n', $activity, '-a', $intentAction,
  '--es', 'request_id', $requestId, '--es', 'panel_action', $Action
)
if ($coordinateActions -contains $Action) { $adbArgs += @('--ei', 'x', $X, '--ei', 'y', $Y) }
if ($Action -eq 'drag') { $adbArgs += @('--ei', 'x', $X, '--ei', 'y', $Y, '--ei', 'x2', $X2, '--ei', 'y2', $Y2) }
if ($Action -eq 'type-text') {
  $shellQuotedText = "'" + $Text.Replace("'", "'\''") + "'"
  $adbArgs += @('--es', 'text', $shellQuotedText)
}

$launchOutput = & adb @adbArgs 2>&1
if ($LASTEXITCODE -ne 0) { throw "ADB activity intent failed: $($launchOutput -join [Environment]::NewLine)" }

$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
$matched = $null
do {
  Start-Sleep -Milliseconds 250
  $window = & adb -s $Serial logcat -d -v brief -s 'SpatialDesktop:I' '*:S' 2>&1
  if ($LASTEXITCODE -ne 0) { throw 'ADB logcat read failed.' }
  $matched = $window | Where-Object { $_ -like "*requestId=$requestId*" -and ($_ -like '*SPATIAL_DESKTOP_DEBUG_ACTION_COMPLETED*' -or $_ -like '*SPATIAL_DESKTOP_DEBUG_ACTION_REJECTED*') } | Select-Object -Last 1
} while (-not $matched -and [DateTimeOffset]::UtcNow -lt $deadline)

if ($EvidenceDirectory) {
  New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
  $receipt = [ordered]@{
    request_id = $requestId
    action = $Action
    presentation = $Presentation
    completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    marker = $matched
  }
  $receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $EvidenceDirectory "$requestId.json") -Encoding utf8
}

if (-not $matched) { throw "Timed out waiting for app marker for request '$requestId'." }
if ($matched -like '*SPATIAL_DESKTOP_DEBUG_ACTION_REJECTED*') {
  Write-Error $matched
  exit 2
}

$matched
if ($Action -eq 'connect') {
  Write-Host 'Connect dispatch completed. Verify SPATIAL_DESKTOP_RFB_STATUS status=connected_loopback-only separately before claiming an RFB session.'
}
