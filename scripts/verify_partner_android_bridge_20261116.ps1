# Compile actual partner bridge using existing Android SDK, no signing/install.
$ErrorActionPreference='Stop'
$branch='work/control-v1-native-bridge-20261116'
$target=Join-Path $env:TEMP 'asterion-owner-bridge-20261116'
$source=Join-Path $target 'Asterion-Writing'
$androidJar=Join-Path $env:LOCALAPPDATA 'Android\Sdk\platforms\android-35\android.jar'
$javac='C:\Program Files\Android\Android Studio\jbr\bin\javac.exe'
if(-not (Test-Path $androidJar)){throw 'Android SDK 35 missing'}
if(-not (Test-Path $javac)){throw 'Original JDK compiler missing'}
if(-not (Test-Path (Join-Path $source '.git'))){
  New-Item -ItemType Directory -Path $target -Force | Out-Null
  & git clone --depth 1 --single-branch --branch $branch 'https://github.com/Azrazieliz/Asterion-Writing.git' $source
  if($LASTEXITCODE -ne 0){throw 'Could not clone canonical Writing partner branch'}
}else{
  & git -C $source fetch --depth 1 origin $branch
  if($LASTEXITCODE -ne 0){throw 'Could not refresh Writing bridge source'}
  & git -C $source reset --hard FETCH_HEAD
  if($LASTEXITCODE -ne 0){throw 'Cannot check out partner HEAD'}
}
$java=Join-Path $source 'app\src\main\java\com\asterion\bridge\AsterionControlBridgeProvider.java'
$manifest=Join-Path $source 'app\src\main\AndroidManifest.xml'
if(-not (Test-Path $java)){throw 'Original bridge class missing'}
[xml]$xml=Get-Content $manifest -Raw
$provider=@($xml.SelectNodes("//*[local-name()='provider']") |
  Where-Object {$_.GetAttribute('name','http://schemas.android.com/apk/res/android') -eq
      'com.asterion.bridge.AsterionControlBridgeProvider'})
if($provider.Count -ne 1){throw 'Bridge provider is not declared exactly once'}
$expected='$'+'{applicationId}.asterion.bridge'
if($provider[0].GetAttribute('authorities','http://schemas.android.com/apk/res/android') -ne $expected){throw 'Provider authority must match installed application ID'}
$out=Join-Path $target 'classes'
New-Item -ItemType Directory -Path $out -Force|Out-Null
& $javac -encoding UTF-8 -source 17 -target 17 -cp $androidJar -d $out $java
if($LASTEXITCODE -ne 0){throw 'Asterion v1 partner provider does not compile with Android SDK 35'}
$compiled=Join-Path $out 'com\asterion\bridge\AsterionControlBridgeProvider.class'
if(-not (Test-Path $compiled)){throw 'Compiled provider bytecode missing'}
$head=(& git -C $source rev-parse HEAD).Trim()
Write-Output "PARTNER_BRIDGE_JAVA_COMPILE_OK repo=Asterion-Writing head=$head signer_pinning=required source_read_only=true manifest_verified=true"
