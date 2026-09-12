[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Serial,
    [Parameter(Mandatory = $true)][ValidateSet('WifiDirect', 'LocalOnlyHotspot')][string]$Mode,
    [ValidateSet('Prepare', 'Collect', 'Cleanup')][string]$Phase = 'Prepare',
    [string]$Adb = '',
    [string]$OutDir = '',
    [int]$CollectWaitSeconds = 75
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$runsRoot = Join-Path $repoRoot 'runs\self-hosted-wireless-adb'
$Adb = if ($Adb) {
    $Adb
} elseif ($env:ANDROID_HOME) {
    Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
} else {
    (Get-Command adb -ErrorAction Stop).Source
}
$package = 'org.questtermuxlab.wirelessadbrecovery'
$activity = "$package/.MainActivity"
$instrumentation = 'io.github.mesmerprism.questquestionnaire.questuiautomation.test/androidx.test.runner.AndroidJUnitRunner'
$termuxFiles = '/data/data/com.termux/files'
$termuxHome = $termuxFiles + '/' + 'home'
$termuxPrefix = $termuxFiles + '/usr'
$termuxStatus = $termuxHome + '/quest-lab/wireless-adb-recovery/status.json'
$modeId = if ($Mode -eq 'WifiDirect') { 'wifi_direct_group_owner' } else { 'local_only_hotspot_owner' }
$startButton = if ($Mode -eq 'WifiDirect') { 'Start Peerless Wi-Fi Direct Probe' } else { 'Start Local-Only Hotspot Probe' }
$pointerPath = Join-Path $runsRoot ("current-{0}.txt" -f $Mode.ToLowerInvariant())

function Invoke-Adb {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int]$TimeoutMs = 120000,
        [switch]$AllowFailure
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Adb
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.ArgumentList.Add('-s')
    $startInfo.ArgumentList.Add($Serial)
    foreach ($argument in $Arguments) {
        $startInfo.ArgumentList.Add([string]$argument)
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutMs)) {
        try { $process.Kill($true) } catch {}
        throw "ADB command timed out: $($Arguments -join ' ')"
    }
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $result = [ordered]@{
        arguments = @($Arguments)
        exit_code = $process.ExitCode
        stdout = $stdout.TrimEnd()
        stderr = $stderr.TrimEnd()
    }
    if (-not $AllowFailure -and $process.ExitCode -ne 0) {
        throw "ADB command failed ($($process.ExitCode)): $($Arguments -join ' ')`n$stderr`n$stdout"
    }
    return $result
}

function Write-JsonFile {
    param([Parameter(Mandatory = $true)][object]$Value, [Parameter(Mandatory = $true)][string]$Path)
    $json = ($Value | ConvertTo-Json -Depth 30) + "`n"
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

function Write-TextFile {
    param([Parameter(Mandatory = $true)][string]$Value, [Parameter(Mandatory = $true)][string]$Path)
    [System.IO.File]::WriteAllText($Path, $Value + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Resolve-RunDirectory {
    if ($OutDir) {
        return [System.IO.Path]::GetFullPath($OutDir)
    }
    if ($Phase -eq 'Prepare') {
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
        return Join-Path $runsRoot ("{0}-{1}" -f $stamp, $Mode.ToLowerInvariant())
    }
    if (-not (Test-Path -LiteralPath $pointerPath)) {
        throw "No current $Mode run pointer exists. Pass -OutDir or run Prepare first."
    }
    return [System.IO.Path]::GetFullPath((Get-Content -LiteralPath $pointerPath -Raw).Trim())
}

function Assert-RunDirectory {
    param([string]$Path)
    $fullRunsRoot = [System.IO.Path]::GetFullPath($runsRoot).TrimEnd('\') + '\'
    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($fullRunsRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Probe output must remain under $runsRoot"
    }
}

function Get-WifiStatus {
    $result = Invoke-Adb -Arguments @('shell', 'cmd', 'wifi', 'status')
    $connected = $result.stdout -match 'Wifi is connected to "([^"]+)"'
    return [ordered]@{
        connected = [bool]$connected
        ssid = if ($connected) { $Matches[1] } else { '' }
        raw = $result.stdout
    }
}

function Get-DeviceSnapshot {
    param([string]$Label)
    $wifi = Get-WifiStatus
    $ip = Invoke-Adb -Arguments @('shell', 'ip', '-4', 'addr', 'show') -AllowFailure
    $setting = Invoke-Adb -Arguments @('shell', 'settings', 'get', 'global', 'adb_wifi_enabled') -AllowFailure
    $tlsPort = Invoke-Adb -Arguments @('shell', 'getprop', 'service.adb.tls.port') -AllowFailure
    $activityState = Invoke-Adb -Arguments @('shell', 'dumpsys', 'activity', 'activities') -AllowFailure
    return [ordered]@{
        label = $Label
        observed_at_utc = [DateTime]::UtcNow.ToString('o')
        wifi = $wifi
        ipv4 = $ip.stdout
        adb_wifi_enabled = $setting.stdout.Trim()
        service_adb_tls_port = $tlsPort.stdout.Trim()
        protected_meta_prompt_visible = [bool]($activityState.stdout -match 'com\.oculus\.os\.vrusb/.WifiDebuggingAlertActivity')
    }
}

function Get-ButtonCenter {
    param([string]$Label)
    $remote = '/data/local/tmp/qtl-self-hosted-probe-ui.xml'
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        [void](Invoke-Adb -Arguments @('shell', 'uiautomator', 'dump', $remote) -AllowFailure)
        $xmlResult = Invoke-Adb -Arguments @('shell', 'cat', $remote) -AllowFailure
        if ($xmlResult.exit_code -eq 0 -and $xmlResult.stdout) {
            try {
                [xml]$xml = $xmlResult.stdout
                $escaped = $Label.Replace("'", "&apos;")
                $node = $xml.SelectSingleNode("//node[@text='$escaped']")
                if ($null -ne $node -and [string]$node.bounds -match '^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$') {
                    return [ordered]@{
                        x = [int](([int]$Matches[1] + [int]$Matches[3]) / 2)
                        y = [int](([int]$Matches[2] + [int]$Matches[4]) / 2)
                        bounds = [string]$node.bounds
                    }
                }
            } catch {}
        }
        [void](Invoke-Adb -Arguments @('shell', 'input', 'swipe', '525', '620', '525', '240', '350') -AllowFailure)
        Start-Sleep -Milliseconds 500
    }
    throw "Could not find helper button '$Label'"
}

function Invoke-HelperButton {
    param([string]$Label)
    [void](Invoke-Adb -Arguments @('shell', 'am', 'start', '-W', '-n', $activity))
    Start-Sleep -Milliseconds 700
    $center = Get-ButtonCenter -Label $Label
    [void](Invoke-Adb -Arguments @('shell', 'input', 'tap', [string]$center.x, [string]$center.y))
    Start-Sleep -Seconds 2
    return $center
}

function Invoke-InfrastructureDisconnect {
    param([string]$Ssid, [string]$RunPath)
    $dry = Invoke-Adb -Arguments @(
        'shell', 'am', 'instrument', '-w',
        '-e', 'scenario', 'settingsWifiDisconnectProbe',
        '-e', 'ssid', $Ssid,
        '-e', 'postDisconnectClickWaitMs', '2500',
        '-e', 'allowDisconnect', 'false',
        $instrumentation
    ) -TimeoutMs 120000 -AllowFailure
    Write-TextFile -Value ($dry.stdout + "`n" + $dry.stderr) -Path (Join-Path $RunPath 'wifi-disconnect-dry.txt')
    if ($dry.exit_code -ne 0) {
        throw 'Settings Wi-Fi disconnect dry probe failed.'
    }
    $mutation = Invoke-Adb -Arguments @(
        'shell', 'am', 'instrument', '-w',
        '-e', 'scenario', 'settingsWifiDisconnectProbe',
        '-e', 'ssid', $Ssid,
        '-e', 'postDisconnectClickWaitMs', '2500',
        '-e', 'allowDisconnect', 'true',
        '-e', 'networkClickMode', 'uiObject2',
        '-e', 'disconnectClickMode', 'uiObject2',
        $instrumentation
    ) -TimeoutMs 120000 -AllowFailure
    Write-TextFile -Value ($mutation.stdout + "`n" + $mutation.stderr) -Path (Join-Path $RunPath 'wifi-disconnect-mutation.txt')
    if ($mutation.exit_code -ne 0) {
        throw 'Settings Wi-Fi disconnect mutation probe failed.'
    }
    Start-Sleep -Seconds 3
}

function Test-SelfHostedAddressPresent {
    param([string]$Ipv4)
    if ($Mode -eq 'WifiDirect') {
        return [bool]($Ipv4 -match '(?ms)p2p0:.*?inet\s+192\.168\.49\.')
    }
    return [bool]($Ipv4 -match '(?ms)(?:wlan[1-9]\d*|ap\d+):.*?inet\s+(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)')
}

function Stop-TermuxRecoveryProcesses {
    $command = "pkill -f '[t]ermux_fleet_agent.py' >/dev/null 2>&1 || true; " +
        "pkill -f '[w]ireless_adb_recovery.py' >/dev/null 2>&1 || true; " +
        'pkill -9 adb >/dev/null 2>&1 || true'
    [void](Invoke-Adb -Arguments @('shell', 'run-as', 'com.termux', 'sh', '-c', $command) -AllowFailure)
}

$runDir = Resolve-RunDirectory
Assert-RunDirectory -Path $runDir
[void](New-Item -ItemType Directory -Force -Path $runDir)
[void](New-Item -ItemType Directory -Force -Path $runsRoot)

$stateResult = Invoke-Adb -Arguments @('get-state')
if ($stateResult.stdout.Trim() -ne 'device') {
    throw "Quest $Serial is not available through serial-scoped ADB."
}

if ($Phase -eq 'Prepare') {
    $pre = Get-DeviceSnapshot -Label 'pre_prepare'
    if (-not [bool]$pre.wifi.connected) {
        throw 'Prepare requires the original infrastructure Wi-Fi association so it can be restored after the probe.'
    }
    $run = [ordered]@{
        schema = 'quest-termux-lab.self-hosted-wireless-adb-probe.private.v1'
        run_id = Split-Path -Leaf $runDir
        serial = $Serial
        mode = $modeId
        phase = 'prepare'
        original_ssid = $pre.wifi.ssid
        prepared_at_utc = [DateTime]::UtcNow.ToString('o')
        pre_snapshot = $pre
    }
    Write-JsonFile -Value $run -Path (Join-Path $runDir 'run.json')
    Write-TextFile -Value $runDir -Path $pointerPath

    [void](Invoke-Adb -Arguments @('shell', 'run-as', 'com.termux', 'rm', '-f', $termuxStatus) -AllowFailure)
    [void](Invoke-Adb -Arguments @('shell', 'settings', 'put', 'global', 'adb_wifi_enabled', '0'))
    Start-Sleep -Seconds 2

    $topologyClick = Invoke-HelperButton -Label $startButton
    $topologyReady = $false
    $topologySnapshot = $null
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        $topologySnapshot = Get-DeviceSnapshot -Label 'topology_starting'
        if (Test-SelfHostedAddressPresent -Ipv4 $topologySnapshot.ipv4) {
            $topologyReady = $true
            break
        }
        Start-Sleep -Milliseconds 600
    }
    if (-not $topologyReady) {
        Write-JsonFile -Value $topologySnapshot -Path (Join-Path $runDir 'topology-not-ready.json')
        throw "$Mode topology did not expose its expected local IPv4 address."
    }
    Write-JsonFile -Value $topologySnapshot -Path (Join-Path $runDir 'topology-ready.json')

    Invoke-InfrastructureDisconnect -Ssid $pre.wifi.ssid -RunPath $runDir
    $disconnected = Get-DeviceSnapshot -Label 'infrastructure_disconnected'
    Write-JsonFile -Value $disconnected -Path (Join-Path $runDir 'infrastructure-disconnected.json')
    if ([bool]$disconnected.wifi.connected) {
        throw 'Infrastructure Wi-Fi remained connected after the guarded Settings disconnect.'
    }
    if (-not (Test-SelfHostedAddressPresent -Ipv4 $disconnected.ipv4)) {
        throw "$Mode topology disappeared when infrastructure Wi-Fi disconnected."
    }

    $restoreClick = Invoke-HelperButton -Label 'Restore Now'
    $promptSnapshot = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $promptSnapshot = Get-DeviceSnapshot -Label 'waiting_for_meta_prompt'
        if ([bool]$promptSnapshot.protected_meta_prompt_visible) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
    Write-JsonFile -Value $promptSnapshot -Path (Join-Path $runDir 'post-restore-request.json')
    $run.phase = 'prepared'
    $run.topology_button = $topologyClick
    $run.restore_button = $restoreClick
    $run.operator_action_required = [bool]$promptSnapshot.protected_meta_prompt_visible
    $run.prepare_status = if ([bool]$promptSnapshot.protected_meta_prompt_visible) {
        'operator_action_required_meta_wifi_debugging_alert'
    } else {
        'restore_dispatched_no_protected_prompt_observed'
    }
    Write-JsonFile -Value $run -Path (Join-Path $runDir 'run.json')
    "RUN_DIR=$runDir"
    "STATUS=$($run.prepare_status)"
    exit 0
}

$runPath = Join-Path $runDir 'run.json'
if (-not (Test-Path -LiteralPath $runPath)) {
    throw "Run metadata is missing: $runPath"
}
$run = Get-Content -LiteralPath $runPath -Raw | ConvertFrom-Json -AsHashtable

if ($Phase -eq 'Collect') {
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1, $CollectWaitSeconds))
    $statusResult = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        $statusResult = Invoke-Adb -Arguments @('shell', 'run-as', 'com.termux', 'cat', $termuxStatus) -AllowFailure
        if ($statusResult.exit_code -eq 0 -and $statusResult.stdout.Trim().StartsWith('{')) {
            break
        }
        Start-Sleep -Seconds 2
    }
    $status = $null
    if ($null -ne $statusResult -and $statusResult.exit_code -eq 0 -and $statusResult.stdout.Trim().StartsWith('{')) {
        Write-TextFile -Value $statusResult.stdout.Trim() -Path (Join-Path $runDir 'termux-status.json')
        $status = $statusResult.stdout | ConvertFrom-Json -AsHashtable
    }
    $snapshot = Get-DeviceSnapshot -Label 'collect'
    Write-JsonFile -Value $snapshot -Path (Join-Path $runDir 'collect-snapshot.json')

    $uidProof = $null
    if ($null -ne $status -and $status.local_adb.target) {
        $target = [string]$status.local_adb.target
        $termuxCommand = 'export HOME=' + $termuxHome + '; ' +
            'export TMPDIR=' + $termuxPrefix + '/tmp; ' +
            $termuxPrefix + '/bin/adb -s ' + $target + ' shell id'
        $uidProof = Invoke-Adb -Arguments @('shell', 'run-as', 'com.termux', 'sh', '-c', $termuxCommand) -AllowFailure
        Write-TextFile -Value ($uidProof.stdout + "`n" + $uidProof.stderr) -Path (Join-Path $runDir 'termux-uid-proof.txt')
    }

    $pass = [bool](
        -not [bool]$snapshot.wifi.connected -and
        (Test-SelfHostedAddressPresent -Ipv4 $snapshot.ipv4) -and
        $null -ne $status -and
        [bool]$status.local_adb.available -and
        [string]$status.local_adb.shell_uid -eq '2000' -and
        $null -ne $uidProof -and
        $uidProof.exit_code -eq 0 -and
        $uidProof.stdout -match 'uid=2000'
    )
    $run.phase = 'collected'
    $run.collected_at_utc = [DateTime]::UtcNow.ToString('o')
    $run.termux_status_present = [bool]($null -ne $status)
    $run.uid_2000_independently_confirmed = [bool]($null -ne $uidProof -and $uidProof.exit_code -eq 0 -and $uidProof.stdout -match 'uid=2000')
    $run.verdict = if ($pass) { 'pass_self_hosted_wireless_adb' } else { 'blocked_no_self_hosted_wireless_adb' }
    Write-JsonFile -Value $run -Path $runPath
    "RUN_DIR=$runDir"
    "VERDICT=$($run.verdict)"
    exit 0
}

if ($Phase -eq 'Cleanup') {
    try {
        [void](Invoke-HelperButton -Label 'Stop Self-Hosted Probe')
    } catch {
        [void](Invoke-Adb -Arguments @('shell', 'am', 'force-stop', $package) -AllowFailure)
    }
    Stop-TermuxRecoveryProcesses
    [void](Invoke-Adb -Arguments @('shell', 'settings', 'put', 'global', 'adb_wifi_enabled', '0') -AllowFailure)
    [void](Invoke-Adb -Arguments @('shell', 'svc', 'wifi', 'disable') -AllowFailure)
    Start-Sleep -Seconds 2
    [void](Invoke-Adb -Arguments @('shell', 'svc', 'wifi', 'enable') -AllowFailure)
    $restored = $null
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        $restored = Get-DeviceSnapshot -Label 'cleanup_restore'
        if ([bool]$restored.wifi.connected -and [string]$restored.wifi.ssid -eq [string]$run.original_ssid) {
            break
        }
        Start-Sleep -Seconds 1
    }
    Write-JsonFile -Value $restored -Path (Join-Path $runDir 'cleanup-snapshot.json')
    $run.phase = 'cleaned'
    $run.cleaned_at_utc = [DateTime]::UtcNow.ToString('o')
    $run.cleanup_original_wifi_restored = [bool](
        $null -ne $restored -and
        [bool]$restored.wifi.connected -and
        [string]$restored.wifi.ssid -eq [string]$run.original_ssid)
    Write-JsonFile -Value $run -Path $runPath
    [void](Invoke-Adb -Arguments @('shell', 'rm', '-f', '/data/local/tmp/qtl-self-hosted-probe-ui.xml') -AllowFailure)
    "RUN_DIR=$runDir"
    "CLEANUP_RESTORED=$($run.cleanup_original_wifi_restored)"
}
