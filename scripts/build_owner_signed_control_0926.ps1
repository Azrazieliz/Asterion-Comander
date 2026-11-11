# Build the ORIGINAL-PACKAGE Asterion Control v0.9.26 source-verified repair release for Samsung.
# Signing identity must match the baseline already installed by the owner.
# Never uninstall, reset data, install via ADB or publish on failure.
param([switch]$PublishToDevBranch)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$branch='work/control-0926-full-path-repair-20261111'
Set-Location $root
$current=(git branch --show-current).Trim()
if($LASTEXITCODE -ne 0 -or $current -ne $branch){throw "Wrong Control branch: $current"}
$dirty=@(git status --porcelain --untracked-files=no)
if($dirty.Count -ne 0){throw 'Tracked changes; refusing unreproducible owner-signed build'}
$local=(git rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0){throw 'Cannot resolve Control HEAD'}
$remote=@(git ls-remote origin ('refs/heads/'+$branch)) | Select-Object -First 1
if($LASTEXITCODE -ne 0 -or -not $remote){throw 'Cannot confirm canonical branch HEAD'}
$expectedSha=($remote -split '\s+')[0].Trim()
if($local -ne $expectedSha){throw 'Stale Control source; fetch latest branch before building'}

$version='0.9.26'
$code=926
$gradleFile=Get-Content (Join-Path $root 'android\app\build.gradle') -Raw
if(-not ($gradleFile -match "versionCode $code") -or
   -not ($gradleFile -match "versionName '$version'") -or
   -not ($gradleFile -match "applicationId 'com.asterion.control'")){
  throw 'Unexpected Control Android version or package ID'
}
$key=Join-Path $HOME '.android\debug.keystore'
if(-not (Test-Path $key)){throw 'Existing owner debug keystore not found; no replacement key permitted'}
$baseline=Join-Path $root 'dist\Asterion-Control-v0.8.6-debug.apk'
if(-not (Test-Path $baseline)){throw 'Original installed-signer baseline missing'}
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
if(-not (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe'))){
  throw 'Original Android Studio Java runtime not available'
}
$env:ANDROID_HOME=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$env:ASTERION_OWNER_KEYSTORE_PATH=$key
$signer=$null
$aapt=$null
foreach($versionName in @('35.0.1','35.0.0','36.1.0','34.0.0','37.0.0')){
  $candidate=Join-Path $env:ANDROID_HOME ('build-tools\'+$versionName)
  if((Test-Path (Join-Path $candidate 'apksigner.bat')) -and
     (Test-Path (Join-Path $candidate 'aapt.exe'))){
    $signer=Join-Path $candidate 'apksigner.bat'
    $aapt=Join-Path $candidate 'aapt.exe'
    break
  }
}
if(-not $signer){throw 'No supported Android apksigner/aapt build-tools installation'}
function Get-Cert([string]$file){
  $certificate=& $signer verify --print-certs $file
  if($LASTEXITCODE -ne 0){throw 'APK certificate validation failed'}
  $value=@($certificate | Where-Object {$_ -match '^Signer #1 certificate SHA-256 digest:'}) |
    Select-Object -First 1
  if(-not $value){throw 'Android signer fingerprint unavailable'}
  return (($value -split ': ',2)[1]).Trim().ToLowerInvariant()
}
$baselineCert=Get-Cert $baseline
$installedCert='9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad'
if($baselineCert -ne $installedCert){throw 'Original baseline certificate mismatch'}
$gradle=@(Get-ChildItem (Join-Path $HOME '.gradle\wrapper\dists') -Filter gradle.bat -File -Recurse |
  Where-Object {$_.FullName -match 'gradle-8\.13\\bin\\gradle\.bat$'} |
  Select-Object -First 1)
if($gradle.Count -ne 1){throw 'Existing Gradle 8.13 installation not found'}
$log=Join-Path $root 'ANDROID_BUILD_v0926.log'
Push-Location (Join-Path $root 'android')
try{
  $ErrorActionPreference='Continue'
  & $gradle[0].FullName :app:assembleRelease --no-daemon --console=plain *> $log
  $result=$LASTEXITCODE
  $ErrorActionPreference='Stop'
}finally{Pop-Location}
if($result -ne 0){
  Get-Content $log -Tail 25
  throw "Owner-signed Android release build failed: $result"
}
$source=Join-Path $root 'android\app\build\outputs\apk\release\app-release.apk'
if(-not (Test-Path $source)){throw 'No release APK produced'}
$releaseCert=Get-Cert $source
if($releaseCert -ne $baselineCert){throw 'INCOMPATIBLE APK: owner signer mismatch'}
$badging=& $aapt dump badging $source
if($LASTEXITCODE -ne 0){throw 'Cannot inspect Android release package metadata'}
$joined=$badging -join "`n"
if($joined -match 'application-debuggable'){throw 'Release APK is debuggable'}
if($joined -notmatch 'package: name=.com\.asterion\.control.'){throw 'Unexpected Android package ID'}
if($joined -notmatch 'versionCode=.926.'){throw 'Unexpected APK version code'}
$dest=Join-Path $root 'dist\Asterion-Control-v0.9.26-release.apk'
Copy-Item $source $dest -Force
$sha=(Get-FileHash $dest -Algorithm SHA256).Hash.ToLowerInvariant()
$size=(Get-Item $dest).Length
[System.IO.File]::WriteAllText((Join-Path $root 'dist\SHA256SUMS-v0.9.26.txt'),
  ($sha+'  Asterion-Control-v0.9.26-release.apk'+ "`n"),
  (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("OWNER_SIGNED_V0926_OK version=$version code=$code bytes=$size sha256=$sha cert=$releaseCert")
if($PublishToDevBranch){
  $remote2=@(git ls-remote origin ('refs/heads/'+$branch))|Select-Object -First 1
  if($LASTEXITCODE -ne 0 -or ($remote2 -split '\s+')[0].Trim() -ne $local){
    throw 'Branch changed during build; refusing stale artifact publish'
  }
  git add -- 'dist/Asterion-Control-v0.9.26-release.apk' 'dist/SHA256SUMS-v0.9.26.txt'
  if($LASTEXITCODE -ne 0){throw 'Cannot stage validated owner-signed artifact'}
  git -c user.name='Asterion Control Build' -c user.email='build@users.noreply.github.com' commit -m 'Publish owner-signer-compatible Control v0.9.26 release APK'
  if($LASTEXITCODE -ne 0){throw 'Cannot commit validated owner-signed artifact'}
  git push origin ('HEAD:'+$branch)
  if($LASTEXITCODE -ne 0){throw 'Cannot upload validated owner-signed artifact'}
  Write-Output ("OWNER_SIGNED_V0926_PUBLISHED sha256=$sha branch=$branch")
}
