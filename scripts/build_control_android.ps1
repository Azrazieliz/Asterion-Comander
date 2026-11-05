# Compile the canonical Android APK on the owner's Windows PC, preserving its debug signing identity.
# Invoke via Asterion Control private GitHub bridge; no ADB or Desktop Commander.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (-not (Test-Path 'android\app\build.gradle')) {throw 'Android source missing'}
$gradle = 'C:\Users\mimim\.gradle\wrapper\dists\gradle-8.13-bin\5xuhj0ry160q40clulazy9h7d\gradle-8.13\bin\gradle.bat'
if (-not (Test-Path $gradle)) {throw 'Installed Gradle 8.13 missing'}
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$version='0.8.4'
if (-not ((Get-Content 'android\app\build.gradle' -Raw) -match "versionName '$version'")) {throw 'Unexpected Android version'}
Set-Location (Join-Path $root 'android')
$ErrorActionPreference='Continue'
& $gradle :app:assembleDebug --offline --no-daemon --console=plain > (Join-Path $root 'ANDROID_BUILD_v084.log') 2>&1
$gradleExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
if ($gradleExit -ne 0) {
  Get-Content (Join-Path $root 'ANDROID_BUILD_v084.log') -Tail 35
  throw 'Gradle build failed'
}
Set-Location $root
New-Item -ItemType Directory 'dist' -Force | Out-Null
$source='android\app\build\outputs\apk\debug\app-debug.apk'
$target='dist\Asterion-Control-v0.8.4-debug.apk'
if (-not (Test-Path $source)) {throw 'APK artifact missing'}
Copy-Item $source $target -Force
$hash=(Get-FileHash $target -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content 'dist\SHA256SUMS-v0.8.4.txt' ($hash+'  Asterion-Control-v0.8.4-debug.apk') -Encoding ASCII
git add -- $target 'dist/SHA256SUMS-v0.8.4.txt'
if ($LASTEXITCODE -ne 0) {throw 'Git stage failed'}
git -c user.name='Asterion Build' -c user.email='build@users.noreply.github.com' commit -m 'Publish independently built Android Control v0.8.4 phone-first pairing repair'
if ($LASTEXITCODE -ne 0) {throw 'Git commit failed'}
git push origin HEAD:main
if ($LASTEXITCODE -ne 0) {throw 'Git upload failed'}
Write-Output "BUILD_OK version=$version bytes=$((Get-Item $target).Length) sha256=$hash commit=$(git rev-parse --short HEAD)"
