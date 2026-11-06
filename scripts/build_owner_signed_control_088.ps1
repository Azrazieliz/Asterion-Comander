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
# An offline/recovered worker must never publish an old Android build.
$localSha=(git rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0){throw 'Local Control source revision unavailable'}
$remoteLine=@(git ls-remote origin ('refs/heads/'+$branch)) | Select-Object -First 1
if($LASTEXITCODE -ne 0 -or -not $remoteLine){throw 'Cannot verify latest approved Control branch'}
$remoteSha=($remoteLine -split '\s+')[0].Trim()
if($localSha -ne $remoteSha){
  throw "STALE_SOURCE: local $localSha differs from current branch $remoteSha. Fetch and retry safely."
}
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

# Optional direct authenticated private-Wi-Fi delivery of the ALREADY signed APK.
# This does not install anything or grant Android package installer approval.
# It may fail harmlessly when the paired Samsung is offline.
try {
  $pairingPath=Join-Path $HOME '.asterion-control\phone-pairing.json'
  if(Test-Path $pairingPath){
    $pair=Get-Content $pairingPath -Raw | ConvertFrom-Json
    $base=[string]$pair.base_url
    $uri=[uri]$base
    $ipv4=$null
    $parsed=[System.Net.IPAddress]::TryParse($uri.Host,[ref]$ipv4)
    if(-not $parsed -or $uri.Scheme -ne 'http' -or $uri.Port -ne 8973 -or
       (-not $ipv4.IsIPv6LinkLocal -and -not
        ($ipv4.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
         ($ipv4.GetAddressBytes()[0] -eq 10 -or
         ($ipv4.GetAddressBytes()[0] -eq 192 -and $ipv4.GetAddressBytes()[1] -eq 168) -or
         ($ipv4.GetAddressBytes()[0] -eq 172 -and $ipv4.GetAddressBytes()[1] -ge 16 -and $ipv4.GetAddressBytes()[1] -le 31) -or
         ($ipv4.GetAddressBytes()[0] -eq 100 -and $ipv4.GetAddressBytes()[1] -ge 64 -and $ipv4.GetAddressBytes()[1] -le 127))))){
      throw 'Paired phone address is not an expected private Android agent'
    }
    $bearer=[string]$pair.token
    if($bearer.Length -lt 32){throw 'Android pairing key missing'}
    $auth=@{Authorization='Bearer '+$bearer}
    $payload=@{name='Asterion-Control-v0.8.8-debug.apk';size=(Get-Item $target).Length;sha256=$sha} | ConvertTo-Json -Compress
    $begin=Invoke-RestMethod -Uri ($base+'/transfer/start') -Headers $auth -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 12
    $transferId=[string]$begin.id
    if($transferId -notmatch '^[A-Za-z0-9_-]{16,80}$'){throw 'Invalid Android transfer receipt'}
    $bytes=[System.IO.File]::ReadAllBytes($target)
    $offset=0
    while($offset -lt $bytes.Length){
      $count=[Math]::Min(524288,$bytes.Length-$offset)
      $part=New-Object byte[] $count
      [Array]::Copy($bytes,$offset,$part,0,$count)
      $chunk=Invoke-RestMethod -Uri ($base+'/transfer/chunk/'+$transferId) -Headers (@{Authorization='Bearer '+$bearer;'X-Transfer-Offset'=[string]$offset}) -Method Put -ContentType 'application/octet-stream' -Body $part -TimeoutSec 30
      if([long]$chunk.received -ne ($offset+$count)){throw 'Phone chunk receipt mismatch'}
      $offset+=$count
    }
    $receipt=Invoke-RestMethod -Uri ($base+'/transfer/finish/'+$transferId) -Headers $auth -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 30
    if(-not $receipt.ok -or $receipt.sha256 -ne $sha -or [long]$receipt.size -ne $bytes.Length){
      throw 'Samsung native transfer receipt did not match checksum'
    }
    Write-Output ('OWNER_SIGNED_APK_DELIVERED_TO_SAMSUNG location='+$receipt.location+' sha256='+$sha)
  }else{
    Write-Output 'OWNER_SIGNED_APK_AVAILABLE_IN_GITHUB; no local phone pairing found'
  }
}catch{
  Write-Warning ('Owner-signed APK retained in GitHub; direct phone delivery deferred: '+$_.Exception.GetType().Name)
}

Write-Output ("OWNER_SIGNED_BUILD_OK version=0.8.8 code=808 bytes="+
  (Get-Item $target).Length+" sha256="+$sha+" cert="+$new+
  " commit="+(git rev-parse --short HEAD))
