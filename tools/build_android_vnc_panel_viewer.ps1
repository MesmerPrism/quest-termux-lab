[CmdletBinding()]
param(
    [string]$ProjectRoot = '',
    [string]$SdkRoot = $env:ANDROID_HOME,
    [string]$JavaHome = $env:JAVA_HOME,
    [string]$OutDir = '',
    [string]$PackageName = 'org.questtermuxlab.vncpanel',
    [string]$OutputBase = 'termux-vnc-panel',
    [int]$MinSdk = 26,
    [switch]$Unsigned
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $SdkRoot) {
    throw 'ANDROID_HOME or -SdkRoot is required.'
}
if (-not $JavaHome) {
    throw 'JAVA_HOME or -JavaHome is required.'
}
if (-not $ProjectRoot) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $ProjectRoot = Join-Path $repoRoot 'examples/android-vnc-panel-viewer'
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not $OutDir) {
    $OutDir = Join-Path $ProjectRoot 'build'
}
$OutDir = (New-Item -ItemType Directory -Force -Path $OutDir).FullName

function Find-LatestChild {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Pattern
    )
    $item = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction Stop |
        Where-Object { $_.Name -like $Pattern } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $item) {
        throw "No matching child found under $Root for $Pattern."
    }
    return $item.FullName
}

$buildTools = Find-LatestChild -Root (Join-Path $SdkRoot 'build-tools') -Pattern '*'
$platform = Find-LatestChild -Root (Join-Path $SdkRoot 'platforms') -Pattern 'android-*'
$androidJar = Join-Path $platform 'android.jar'
$aapt2 = Join-Path $buildTools 'aapt2.exe'
$d8 = Join-Path $buildTools 'd8.bat'
$zipalign = Join-Path $buildTools 'zipalign.exe'
$apksigner = Join-Path $buildTools 'apksigner.bat'
$javac = Join-Path $JavaHome 'bin/javac.exe'
$jar = Join-Path $JavaHome 'bin/jar.exe'
$keytool = Join-Path $JavaHome 'bin/keytool.exe'

foreach ($tool in @($androidJar, $aapt2, $d8, $zipalign, $javac, $jar)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Required Android build tool not found: $tool"
    }
}
if (-not $Unsigned) {
    foreach ($tool in @($apksigner, $keytool)) {
        if (-not (Test-Path -LiteralPath $tool)) {
            throw "Required signing tool not found: $tool"
        }
    }
}

$genDir = New-Item -ItemType Directory -Force -Path (Join-Path $OutDir 'gen')
$classesDir = New-Item -ItemType Directory -Force -Path (Join-Path $OutDir 'classes')
$dexDir = New-Item -ItemType Directory -Force -Path (Join-Path $OutDir 'dex')
$unsignedApk = Join-Path $OutDir "$OutputBase-unsigned.apk"
$dexedApk = Join-Path $OutDir "$OutputBase-dexed.apk"
$alignedApk = Join-Path $OutDir "$OutputBase-aligned.apk"
$signedApk = Join-Path $OutDir "$OutputBase-debug.apk"

Remove-Item -LiteralPath $unsignedApk, $dexedApk, $alignedApk, $signedApk -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $classesDir.FullName '*') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $dexDir.FullName '*') -Recurse -Force -ErrorAction SilentlyContinue

$manifest = Join-Path $ProjectRoot 'AndroidManifest.xml'
$sourceRoot = Join-Path $ProjectRoot 'src'
$javaSources = Get-ChildItem -LiteralPath $sourceRoot -Recurse -Filter '*.java' | Select-Object -ExpandProperty FullName
if (-not $javaSources) {
    throw "No Java sources found under $sourceRoot."
}

& $aapt2 link `
    --manifest $manifest `
    -I $androidJar `
    --java $genDir.FullName `
    --min-sdk-version $MinSdk `
    --target-sdk-version 35 `
    --rename-manifest-package $PackageName `
    -o $unsignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'aapt2 link failed.'
}

& $javac `
    -encoding UTF-8 `
    -source 8 `
    -target 8 `
    -classpath "$androidJar;$($genDir.FullName)" `
    -d $classesDir.FullName `
    $javaSources
if ($LASTEXITCODE -ne 0) {
    throw 'javac failed.'
}

$classFiles = Get-ChildItem -LiteralPath $classesDir.FullName -Recurse -Filter '*.class' | Select-Object -ExpandProperty FullName
if (-not $classFiles) {
    throw "No class files produced under $($classesDir.FullName)."
}

& $d8 `
    --min-api $MinSdk `
    --output $dexDir.FullName `
    $classFiles
if ($LASTEXITCODE -ne 0) {
    throw 'd8 failed.'
}

Copy-Item -LiteralPath $unsignedApk -Destination $dexedApk -Force
& $jar uf $dexedApk -C $dexDir.FullName classes.dex
if ($LASTEXITCODE -ne 0) {
    throw 'jar update failed.'
}

& $zipalign -f 4 $dexedApk $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'zipalign failed.'
}

if ($Unsigned) {
    Write-Output $alignedApk
    return
}

$debugKeystore = Join-Path $OutDir 'debug.keystore'
if (-not (Test-Path -LiteralPath $debugKeystore)) {
    & $keytool `
        -genkeypair `
        -keystore $debugKeystore `
        -storepass android `
        -keypass android `
        -alias androiddebugkey `
        -keyalg RSA `
        -keysize 2048 `
        -validity 10000 `
        -dname 'CN=Android Debug,O=Quest Termux Lab,C=US'
    if ($LASTEXITCODE -ne 0) {
        throw 'debug keystore generation failed.'
    }
}

& $apksigner sign `
    --ks $debugKeystore `
    --ks-pass pass:android `
    --key-pass pass:android `
    --out $signedApk `
    $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'apksigner failed.'
}

Write-Output $signedApk
