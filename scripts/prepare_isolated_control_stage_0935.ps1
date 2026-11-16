# Prepare isolated D: checkout from the canonical Control source.
# Refuse any existing unexpected stage instead of destroying files.
$ErrorActionPreference='Stop'
$target='D:\AsterionControlModelStage\control-source'
$branch='work/control-0927-overnight-cycles-20261111'
$base=Split-Path -Parent $target
if(Test-Path $target){
 if(-not(Test-Path (Join-Path $target '.git'))){
   throw 'D target already exists but is not Control checkout; untouched'
 }
 $orig=(& git -C $target remote get-url origin).Trim()
 if($orig -notmatch '(?i)Azrazieliz/Asterion-Comander(\.git)?$'){
   throw 'D source remote not canonical; untouched'
 }
}else{
 New-Item -ItemType Directory -Path $base -Force | Out-Null
 & git clone --depth 1 --single-branch --branch $branch 'https://github.com/Azrazieliz/Asterion-Comander.git' $target
 if($LASTEXITCODE -ne 0){throw 'Failed to clone isolated Control source'}
}
& git -C $target fetch --depth 1 origin $branch
if($LASTEXITCODE -ne 0){throw 'Failed fetching canonical branch'}
& git -C $target reset --hard FETCH_HEAD
if($LASTEXITCODE -ne 0){throw 'Could not select canonical HEAD'}
$current=(& git -C $target rev-parse HEAD).Trim()
$bytes=(Get-Item $target).FullName
Write-Output ('ISOLATED_CONTROL_STAGE_OK path='+$target+' head='+$current)
