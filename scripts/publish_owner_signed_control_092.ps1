# Publish the already verified owner-signed v0.9.2 APK into the existing
# Android in-app update feed. No installation, data reset or APK re-signing.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$apk=Join-Path $root 'dist\Asterion-Control-v0.9.2-release.apk'
if(-not (Test-Path $apk)){throw 'Verified release APK unavailable'}
$expected=(Get-Content (Join-Path $root 'dist\SHA256SUMS-v0.9.2.txt') -Raw).Split(' ')[0].Trim().ToLowerInvariant()
$actual=(Get-FileHash $apk -Algorithm SHA256).Hash.ToLowerInvariant()
if($expected.Length -ne 64 -or $expected -ne $actual){throw 'Release checksum mismatch'}
$buildTools=Join-Path $env:LOCALAPPDATA 'Android\Sdk\build-tools'
$apksigner=$null
foreach($v in @('35.0.1','35.0.0','36.1.0','34.0.0','37.0.0')){
  $candidate=Join-Path $buildTools ($v+'\apksigner.bat')
  if(Test-Path $candidate){$apksigner=$candidate;break}
}
if(-not $apksigner){throw 'Cannot independently verify release APK signer'}
$printed=& $apksigner verify --print-certs $apk
if($LASTEXITCODE -ne 0){throw 'APK signature invalid'}
$line=@($printed|Where-Object {$_ -match '^Signer #1 certificate SHA-256 digest:'})|Select-Object -First 1
if(-not $line){throw 'APK signer fingerprint absent'}
$cert=(($line -split ': ',2)[1]).Trim().ToLowerInvariant()
if($cert -ne '9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad'){
  throw 'APK signer differs from original installed app'
}
$feedDir='D:\AsterionControlV092Feed'
if(Test-Path $feedDir){throw 'Feed release directory already exists; refusing to overwrite'}
git clone --quiet --single-branch --branch main https://github.com/Azrazieliz/Asterion-Comander.git $feedDir
if($LASTEXITCODE -ne 0){throw 'Cannot read existing canonical update feed'}
$feed=Join-Path $feedDir 'dist'
$latestPath=Join-Path $feed 'latest-release.json'
if(-not (Test-Path $latestPath)){throw 'Canonical release manifest unavailable'}
$latest=Get-Content $latestPath -Raw|ConvertFrom-Json
if([int]$latest.version_code -ge 902){throw 'Main feed is already at v0.9.2 or newer'}
$publish=Join-Path $feed 'Asterion-Control-v0.9.2-release.apk'
Copy-Item -Path $apk -Destination $publish
Copy-Item -Path $apk -Destination (Join-Path $feed 'Asterion-Control-v0.9.2-debug.apk')
Copy-Item (Join-Path $root 'dist\SHA256SUMS-v0.9.2.txt') (Join-Path $feed 'SHA256SUMS-v0.9.2.txt')
$baseUrl='https://raw.githubusercontent.com/Azrazieliz/Asterion-Comander/main/dist/'
$manifest=[ordered]@{
  version_code=902
  version_name='0.9.2'
  apk_url=$baseUrl+'Asterion-Control-v0.9.2-release.apk'
  sha256=$actual
  size_bytes=(Get-Item $apk).Length
}
$utf8=New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($latestPath,($manifest|ConvertTo-Json -Depth 6)+ "`n",$utf8)
$legacy=[ordered]@{
  version_code=902
  version_name='0.9.2'
  apk_url=$baseUrl+'Asterion-Control-v0.9.2-debug.apk'
  sha256=$actual
  size_bytes=(Get-Item $apk).Length
}
[System.IO.File]::WriteAllText((Join-Path $feed 'latest.json'),($legacy|ConvertTo-Json -Depth 6)+"`n",$utf8)
$files=@('dist/latest-release.json','dist/latest.json',
         'dist/Asterion-Control-v0.9.2-release.apk',
         'dist/Asterion-Control-v0.9.2-debug.apk',
         'dist/SHA256SUMS-v0.9.2.txt')
git -C $feedDir add -- $files
if($LASTEXITCODE -ne 0){throw 'Cannot stage verified update-feed files'}
git -C $feedDir -c user.name='Asterion Control Release' -c user.email='build@users.noreply.github.com' commit -m 'Publish original-signed Asterion Control v0.9.2 update'
if($LASTEXITCODE -ne 0){throw 'Cannot commit new update feed'}
git -C $feedDir push origin HEAD:main
if($LASTEXITCODE -ne 0){throw 'Cannot publish update feed'}
Write-Output ('CONTROL_UPDATE_FEED_PUBLISHED version=0.9.2 sha256='+$actual)
