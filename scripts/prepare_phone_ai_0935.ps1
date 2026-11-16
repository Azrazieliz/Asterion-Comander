# Build pinned llama.cpp arm64 in an isolated D: checkout, and download
# a verified GGUF as an uncompressed APK-owned asset. Never touch live agents.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$native=Join-Path $root 'android\app\src\main\jniLibs\arm64-v8a\libasterion_llm.so'
$weights=Join-Path $root 'android\app\src\main\assets\models\Qwen3-0.6B-Q4_K_M.gguf'
$expected='373db06783953f0981572d008f183eb2167b93304f5adbf7c4ce6ed6a91ee437'
$size=484220288L
$stage='D:\AsterionControlModelStage'
$ndk=Join-Path $env:LOCALAPPDATA 'Android\Sdk\ndk\27.2.12479018'
if(-not(Test-Path (Join-Path $ndk 'build\cmake\android.toolchain.cmake'))){
 throw 'Original Android NDK 27.2 not present'
}
$cmake=Get-Command cmake -ErrorAction Stop
$ninja=Get-Command ninja -ErrorAction Stop
$version='1d2e880bad3f4f2adced6c9f5a3ecf035f7f0f61'
$third=Join-Path $stage 'third_party\llama.cpp'
$build=Join-Path $stage 'native-build'
New-Item -ItemType Directory -Path $stage -Force|Out-Null
if(-not(Test-Path (Join-Path $third '.git'))){
 New-Item -ItemType Directory -Path $third -Force|Out-Null
 & git -C $third init -q
 if($LASTEXITCODE -ne 0){throw 'llama.cpp init failed'}
 & git -C $third remote add origin 'https://github.com/ggml-org/llama.cpp.git'
 if($LASTEXITCODE -ne 0){throw 'llama.cpp remote failed'}
}
& git -C $third fetch --depth 1 origin $version
if($LASTEXITCODE -ne 0){throw 'Unable to fetch exact pinned llama.cpp commit'}
& git -C $third checkout --detach -f $version
if($LASTEXITCODE -ne 0){throw 'Unable to pin source tree'}
if((git -C $third rev-parse HEAD).Trim() -ne $version){throw 'Pinned source SHA mismatch'}
New-Item -ItemType Directory -Path (Split-Path $native) -Force|Out-Null
$env:TEMP=Join-Path $stage 'temp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force|Out-Null
$cmakeSource=Join-Path $root 'android\app\src\main\cpp'
$args1=@('-S',$cmakeSource,'-B',$build,'-G','Ninja',
 '-DCMAKE_BUILD_TYPE=Release',
 ('-DCMAKE_TOOLCHAIN_FILE='+(Join-Path $ndk 'build\cmake\android.toolchain.cmake')),
 '-DANDROID_ABI=arm64-v8a','-DANDROID_PLATFORM=android-29',
 '-DANDROID_STL=c++_static',('-DLLAMA_SOURCE_DIR='+$third))
& $cmake.Source @args1
if($LASTEXITCODE -ne 0){throw 'Native Android inference configuration failed'}
& $cmake.Source --build $build --target asterion_llm --parallel 3
if($LASTEXITCODE -ne 0){throw 'Real llama.cpp Android JNI compilation failed'}
$lib=Join-Path $build 'libasterion_llm.so'
if(-not(Test-Path $lib)){throw 'No native shared library emitted'}
if((Get-Item $lib).Length -lt 100000){throw 'Native shared library too small'}
Copy-Item -LiteralPath $lib -Destination $native -Force
$libHash=(Get-FileHash $native -Algorithm SHA256).Hash.ToLowerInvariant()
New-Item -ItemType Directory -Path (Split-Path $weights) -Force|Out-Null
if((Test-Path $weights) -and (Get-Item $weights).Length -eq $size -and
   (Get-FileHash $weights -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected){
 Write-Output 'EMBEDDED_MODEL_ALREADY_SHA_VERIFIED'
}else{
 $partial=$weights+'.partial'
 if(Test-Path $partial){throw 'Preexisting partial model: inspect instead of overwriting'}
 $url='https://huggingface.co/tauqir02/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf'
 & curl.exe --fail --location --retry 3 --connect-timeout 20 --output $partial $url
 if($LASTEXITCODE -ne 0){throw 'GGUF download incomplete; partial preserved for diagnostics'}
 if((Get-Item $partial).Length -ne $size -or
   (Get-FileHash $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){
 throw 'GGUF size or SHA failed; refusing to package'
 }
 Move-Item -LiteralPath $partial -Destination $weights
}
if((Get-FileHash $weights -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){
 throw 'Final GGUF checksum failed'
}
Write-Output ('PHONE_HEAD_NATIVE_AND_MODEL_READY sha256='+$expected+
 ' bytes='+$size+' runtime_sha256='+$libHash+' pinned_llama='+$version+
 ' staging='+$root+' installed_phone=false')
