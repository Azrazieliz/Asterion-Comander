# Source-only Android compile, never sign, publish, install or touch the paired phone.
# Execute from an isolated checkout on the existing Windows development machine.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
if(-not (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe'))){
  throw 'Android Studio Java runtime unavailable'
}
if(-not (Test-Path $env:ANDROID_HOME)){
  throw 'Android SDK unavailable'
}
$gradle=@(Get-ChildItem (Join-Path $HOME '.gradle\wrapper\dists') -Filter gradle.bat -Recurse -File |
  Where-Object {$_.FullName -match 'gradle-8\.13\\bin\\gradle\.bat$'} |
  Select-Object -First 1)
if($gradle.Count -ne 1){throw 'Existing Gradle 8.13 runtime not found'}
Push-Location (Join-Path $root 'android')
try{
  & $gradle[0].FullName :app:compileDebugJavaWithJavac --offline --no-daemon --console=plain
  $result=$LASTEXITCODE
}finally{Pop-Location}
if($result -ne 0){throw "Android Java compilation failed with code $result"}
Write-Output 'ANDROID_DIAGNOSTICS_COMPILE_OK (source-only; not signed or installed)'
