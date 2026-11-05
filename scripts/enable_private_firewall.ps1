# One-time Windows approval. Control remains private to the local network.
$ErrorActionPreference='Stop'
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$admin=(New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $admin){throw 'Administrator approval required for private firewall rules'}
$rules=@(@{Name='Asterion-Control-PC';Protocol='TCP';Port=8911},@{Name='Asterion-Control-Discovery';Protocol='UDP';Port=8912})
foreach($rule in $rules){
  if(-not(Get-NetFirewallRule -Name $rule.Name -ErrorAction SilentlyContinue)){
    New-NetFirewallRule -Name $rule.Name -DisplayName $rule.Name -Direction Inbound -Action Allow -Enabled True -Profile Private -Protocol $rule.Protocol -LocalPort $rule.Port -RemoteAddress LocalSubnet | Out-Null
  }
}
Write-Host 'Asterion Control: private-LAN access authorized. No public port forwarding.'
