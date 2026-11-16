# Compile every independently authored partner provider against the installed
# Android SDK; no production app, keystore, APK or private data is modified.
$ErrorActionPreference='Stop'
$branch='work/control-v1-native-bridge-20261116'
$workspace=Join-Path $env:TEMP 'asterion-all-owner-bridges-20261116'
$androidJar=Join-Path $env:LOCALAPPDATA 'Android\Sdk\platforms\android-35\android.jar'
$javac='C:\Program Files\Android\Android Studio\jbr\bin\javac.exe'
if(-not(Test-Path $androidJar) -or -not(Test-Path $javac)){throw 'Existing Android SDK/JDK unavailable'}
$specs=@(
  @('AsterionDownloader','app'),
  @('AsterionArt','app'),
  @('Asterion-Core','android_app/app'),
  @('Asterion-Writing','app'),
  @('Asterion-Games','app')
)
New-Item -ItemType Directory -Path $workspace -Force | Out-Null
foreach($spec in $specs){
  $name=$spec[0];$module=$spec[1]
  $target=Join-Path $workspace $name
  if(-not(Test-Path (Join-Path $target '.git'))){
    & git clone --depth 1 --single-branch --branch $branch ('https://github.com/Azrazieliz/'+$name+'.git') $target
    if($LASTEXITCODE -ne 0){throw "Failed to clone $name"}
  }else{
    & git -C $target fetch --depth 1 origin $branch
    if($LASTEXITCODE -ne 0){throw "Failed fetching $name"}
    & git -C $target reset --hard FETCH_HEAD
    if($LASTEXITCODE -ne 0){throw "Failed selecting $name"}
  }
  $java=Join-Path $target ($module+'/src/main/java/com/asterion/bridge/AsterionControlBridgeProvider.java')
  $manifest=Join-Path $target ($module+'/src/main/AndroidManifest.xml')
  if(-not(Test-Path $java) -or -not(Test-Path $manifest)){throw "Missing $name partner bridge or manifest"}
  [xml]$xml=Get-Content $manifest -Raw
  $providers=@($xml.SelectNodes("//*[local-name()='provider']")|
    Where-Object {$_.GetAttribute('name','http://schemas.android.com/apk/res/android') -eq
      'com.asterion.bridge.AsterionControlBridgeProvider'})
  if($providers.Count -ne 1){throw "$name missing exactly one native provider"}
  $expected='$'+'{applicationId}.asterion.bridge'
  if($providers[0].GetAttribute('authorities','http://schemas.android.com/apk/res/android') -ne $expected){throw "$name authority mismatch"}
  $out=Join-Path $workspace ('classes-'+$name)
  New-Item -ItemType Directory -Path $out -Force | Out-Null
  & $javac -encoding UTF-8 -source 17 -target 17 -cp $androidJar -d $out $java
  if($LASTEXITCODE -ne 0){throw "$name native bridge does not compile"}
  if(-not(Test-Path (Join-Path $out 'com/asterion/bridge/AsterionControlBridgeProvider.class'))){throw "$name class missing"}
  $sha=(& git -C $target rev-parse HEAD).Trim()
  Write-Output "ASTERION_PARTNER_COMPILE_OK project=$name head=$sha native_auth=true source_only=true"
}
Write-Output 'FIVE_PARTNER_PROVIDER_COMPILES_OK; no APKs built or installed'
