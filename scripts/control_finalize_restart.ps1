# Finalize an explicitly requested force-reinitialize after the originating API job exits.
# Refuse restarting an in-use worker. No token rotation, clearing, or re-pairing.
param([ValidatePattern('^[0-9a-f]{32}$')][string]$RepairId)
$ErrorActionPreference='Stop'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$file=Join-Path $state 'full-repair.json'
function Save-Result([string]$phase,[bool]$ok,[string]$problem,[hashtable]$steps){
  $payload=[ordered]@{id=$RepairId;mode='force';phase=$phase;ok=$ok;
    updated=([DateTimeOffset]::UtcNow.ToUnixTimeSeconds());steps=$steps;error=$problem}
  $temp=$file+'.new'
  [IO.File]::WriteAllText($temp,($payload|ConvertTo-Json -Depth 8 -Compress),
    (New-Object System.Text.UTF8Encoding($false)))
  Move-Item $temp $file -Force
}
Start-Sleep -Seconds 8
try{
  $receipt=Get-Content $file -Raw | ConvertFrom-Json
  if($receipt.id -ne $RepairId -or $receipt.mode -ne 'force'){exit 2}
  $steps=@{}
  foreach($property in $receipt.steps.PSObject.Properties){$steps[$property.Name]=$property.Value}
  & (Join-Path $PSScriptRoot 'restart_control_worker.ps1') | Out-Null
  $steps['windows_restart']='executed; verifying'
  $token=(Get-Content (Join-Path $state 'control-token.txt') -Raw).Trim()
  $url=(Get-Content (Join-Path $state 'agent-host.txt') -Raw).Trim()
  $headers=@{Authorization=('Bearer '+$token)}
  $worker=$false;$phone=$false;$direct=$false;$accessible=$false;$capture=$false
  for($i=0;$i -lt 20;$i++){
    try{
      $w=Invoke-RestMethod ($url+'/api/v1/health') -Headers $headers -TimeoutSec 2
      $worker=[bool]$w.ok
      if($worker){
        $p=Invoke-RestMethod ($url+'/api/v1/phone') -Headers $headers -TimeoutSec 4
        $phone=[bool]($p.paired -and $p.reachable)
        if($phone){
          $direct=[bool]($p.info.remote_transport.direct_mcp.connected -and
            $p.info.remote_transport.direct_mcp.transport -eq 'direct_wss')
          $accessible=[bool]$p.info.accessible
          $capture=[bool]$p.info.capture
          if($direct){break}
        }
      }
    }catch{}
    Start-Sleep -Milliseconds 650
  }
  $steps['windows_worker']=if($worker){'verified'}else{'unreachable'}
  $steps['phone_listener']=if($phone){'verified'}else{'unreachable'}
  $steps['native_websocket']=if($direct){'verified'}else{'not_connected'}
  $steps['accessibility']=if($accessible){'verified'}else{'android_permission_required'}
  $steps['live_video']=if($capture){'capture_active'}else{'android_media_projection_consent_required'}
  $steps['windows_restart']='completed'
  $verified=$worker -and $phone -and $direct -and $accessible -and $capture
  if($verified){Save-Result 'verified' $true '' $steps}
  elseif($worker -and $phone -and $direct -and $accessible -and -not $capture){
    Save-Result 'permission_required' $false 'Android screen-sharing approval is required' $steps
  }else{Save-Result 'partial' $false 'Full direct path could not be verified after Windows restart' $steps}
}catch{
  $steps=@{windows_restart='blocked_or_failed';credentials='preserved'}
  Save-Result 'partial' $false $_.Exception.Message $steps
  exit 1
}
