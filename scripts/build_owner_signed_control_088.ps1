# Asterion Control 0.8.8 — owner-signed non-destructive Android update package.
# Use the SAME Windows debug keystore used for the installed 0.8.6 APK.
# No ADB, uninstall, wipe, second package name, paid API or separate AI model.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$branch='work/android-primary-continuation-observation-20261105'
Set-Location $root
$current=(git branch --show-current).Trim()
if($LASTEXITCODE -ne 0 -or $current -ne $branch){throw "Wrong branch: $current"}
$tracked=@(git status --porcelain --untracked-files=no)
if($tracked.Count -gt 0){throw 'Tracked modifications prevent reproducible signed build'}
$gradle='C:\Users\mimim\.gradle\wrapper\dists\gradle-8.13-bin\5xuhj0ry160q40clulazy9h7d\gradle-8.13\bin\gradle.bat'
if(-not (Test-Path $gradle)){throw 'Owner Gradle 8.13 is unavailable'}
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$version='0.8.8'
$versionCode=808
$settings=Get-Content 'android\app\build.gradle' -Raw
if(-not ($settings -match "versionName '$version'") -or -not ($settings -match "versionCode $versionCode")){
  throw 'Unexpected APK version configuration'
}
$signer=Join-Path $env:ANDROID_HOME 'build-tools\35.0.0\apksigner.bat'
if(-not (Test-Path $signer)){throw 'Android apksigner 35.0.0 missing'}
$baseline=Join-Path $root 'dist\Asterion-Control-v0.8.6-debug.apk'
if(-not (Test-Path $baseline)){throw 'Original signed 0.8.6 baseline missing'}
function Get-SignerDigest([string]$file){
  $details=& $signer verify --print-certs $file
  if($LASTEXITCODE -ne 0){throw "APK signature verification failed for $file"}
  $line=@($details | Where-Object {$_ -match '^Signer #1 certificate SHA-256 digest:'}) | Select-Object -First 1
  if(-not $line){throw 'Android signing certificate not reported'}
  return (($line -split ': ',2)[1]).Trim().ToLowerInvariant()
}
$original=Get-SignerDigest $baseline
$expected='9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad'
if($original -ne $expected){throw 'Baseline signer differs from owner-installed 0.8.6 certificate'}
Set-Location (Join-Path $root 'android')
$ErrorActionPreference='Continue'
& $gradle :app:assembleDebug --offline --no-daemon --console=plain *> (Join-Path $root 'ANDROID_BUILD_v088.log')
$exit=$LASTEXITCODE
$ErrorActionPreference='Stop'
Set-Location $root
if($exit -ne 0){
  Get-Content (Join-Path $root 'ANDROID_BUILD_v088.log') -Tail 40
  throw "Android v0.8.8 build failed: $exit"
}
$source=Join-Path $root 'android\app\build\outputs\apk\debug\app-debug.apk'
if(-not (Test-Path $source)){throw 'Gradle did not generate APK'}
$new=Get-SignerDigest $source
if($new -ne $original){
  throw "CERTIFICATE_MISMATCH: old=$original new=$new — update cannot replace installed 0.8.6"
}
$target=Join-Path $root 'dist\Asterion-Control-v0.8.8-debug.apk'
Copy-Item $source $target -Force
$sha=(Get-FileHash $target -Algorithm SHA256).Hash.ToLowerInvariant()
$sum=Join-Path $root 'dist\SHA256SUMS-v0.8.8.txt'
[System.IO.File]::WriteAllText($sum,($sha+'  Asterion-Control-v0.8.8-debug.apk'+"\n"),
  (New-Object System.Text.UTF8Encoding($false)))
git add -- 'dist/Asterion-Control-v0.8.8-debug.apk' 'dist/SHA256SUMS-v0.8.8.txt'
if($LASTEXITCODE -ne 0){throw 'Failed to stage signed APK'}
git -c user.name='Asterion Build' -c user.email='build@users.noreply.github.com' commit -m 'Publish owner-signer-compatible Android Control v0.8.8 APK'
if($LASTEXITCODE -ne 0){throw 'Failed to commit signed package'}
git push origin ('HEAD:'+ $branch)
if($LASTEXITCODE -ne 0){throw 'Signed Android package upload failed'}
Write-Output ("OWNER_SIGNED_BUILD_OK version=0.8.8 code=808 bytes="+
  (Get-Item $target).Length+" sha256="+$sha+" cert="+$new+
  " commit="+(git rev-parse --short HEAD))
