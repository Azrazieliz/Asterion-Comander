# Owner-only, backup-first hard recovery of Asterion Control's PRIVATE Git relay.
# Never touches native Windows Control, Android pairing, ADB, credentials, or native jobs.
$ErrorActionPreference = 'Stop'
$state = Join-Path $env:LOCALAPPDATA 'AsterionControl'
$production = 'D:\AsterionControlRelease'
$repo = Join-Path $state 'private-bridge-repo'
$guard = Join-Path $state 'control-relay-maintenance.lock'
$watchdog = Join-Path $production 'scripts\control_repair_watchdog.ps1'
$launcher = Join-Path $production 'scripts\start_git_bridge.ps1'
$task = 'Asterion Control Self-Healing Worker'
$url = 'https://github.com/Azrazieliz/Asterion-Control-Bridge.git'
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$staging = Join-Path $state ('private-bridge-repo-stage-' + $stamp)
$backup = Join-Path $state ('private-bridge-repo-backup-' + $stamp)
$switched = $false
$success = $false
$recovered = 0
$uncertain = 0
if (!(Test-Path $launcher)) { throw 'Original Control supervisor missing; refusing recovery' }
if (!(Test-Path $watchdog)) { throw 'Original Control watchdog missing; refusing recovery' }
if ((Get-Content $watchdog -Raw) -notmatch 'control-relay-maintenance\.lock') {
    throw 'Install updated watchdog first; no processes stopped'
}
if (Test-Path $guard) { throw 'Another relay maintenance session is already active' }
if (!(Test-Path (Join-Path $state 'control-token.txt'))) {
    throw 'Original credentials missing; refusing recovery'
}
$healthPath = Join-Path $state 'control-git-bridge-health.json'
if (Test-Path $healthPath) {
    $health = Get-Content $healthPath -Raw | ConvertFrom-Json
    if ($health.inflight_id) { throw 'Unknown in-flight operation; refusing unsafe replay' }
}
# Clone BEFORE interrupting existing processes; the old Git checkout stays untouched
# until a new, authenticated, clean worktree has been fully downloaded.
& git clone --quiet --depth 1 --single-branch --branch main $url $staging
if ($LASTEXITCODE -ne 0 -or !(Test-Path (Join-Path $staging '.git'))) {
    throw 'Clean private bridge clone failed; original installation unchanged'
}
$remote = (& git -C $staging remote get-url origin).Trim().ToLowerInvariant().TrimEnd('/')
if ($remote -notin @('https://github.com/azrazieliz/asterion-control-bridge.git',
                     'https://github.com/azrazieliz/asterion-control-bridge')) {
    throw 'Unexpected bridge origin; original installation unchanged'
}
New-Item -ItemType File -Path $guard -ErrorAction Stop | Out-Null
try {
    # Stop every Git relay supervisor, THEN every logical Git relay Python
    # process. No native Control service, browser, ADB, or unrelated worker.
    $supervisors = @(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.Name -match '^(powershell|pwsh)\.exe$' -and
            $_.CommandLine -match '(?i)start_git_bridge\.ps1'
        })
    foreach ($p in $supervisors) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop }
        catch [Microsoft.PowerShell.Commands.ProcessCommandException] {}
    }
    $workers = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object {
            $_.CommandLine -match '(?i)(^|\s)-m\s+asterion_remote\.github_bridge_git(\s|$)'
        })
    foreach ($p in $workers) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop }
        catch [Microsoft.PowerShell.Commands.ProcessCommandException] {}
    }
    Start-Sleep -Seconds 2
    $remaining = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object {
            $_.CommandLine -match '(?i)(^|\s)-m\s+asterion_remote\.github_bridge_git(\s|$)'
        })
    if ($remaining.Count) { throw 'Some old Git relay processes are still alive' }

    if (Test-Path $repo) {
        # Rename, not delete: preserves reflog, local commits, rebase state,
        # .pending journals, and exact receipt bytes for later inspection.
        Move-Item -LiteralPath $repo -Destination $backup -ErrorAction Stop
    }
    Move-Item -LiteralPath $staging -Destination $repo -ErrorAction Stop
    $switched = $true

    $oldResults = Join-Path $backup 'results'
    $newResults = Join-Path $repo 'results'
    New-Item -ItemType Directory -Path $newResults -Force | Out-Null
    $terminal = @('complete','error','failed','uncertain','skipped')
    if (Test-Path $oldResults) {
        foreach ($old in Get-ChildItem -LiteralPath $oldResults -Filter '*.json' -File) {
            try {
                $prior = Get-Content -LiteralPath $old.FullName -Raw | ConvertFrom-Json
                if ($prior.id -ne $old.BaseName -or !$prior.status) { continue }
            } catch { continue } # Original unchanged in immutable full backup
            $target = Join-Path $newResults $old.Name
            if (Test-Path $target) {
                try {
                    $published = Get-Content -LiteralPath $target -Raw | ConvertFrom-Json
                    if ($published.id -ne $old.BaseName) { throw 'Remote identity mismatch' }
                    if ($published.status -in $terminal -or $prior.status -notin $terminal) {
                        continue # Never replace published final results
                    }
                } catch {
                    throw ('Published receipt invalid; backup untouched: ' + $old.Name)
                }
            }
            Copy-Item -LiteralPath $old.FullName -Destination $target -Force
            $recovered++
        }
        # A .pending marker may represent an action that already started. If
        # there is no final receipt, record an uncertain outcome, never replay.
        foreach ($marker in Get-ChildItem -LiteralPath $oldResults -Filter '*.pending' -File) {
            $target = Join-Path $newResults ($marker.BaseName + '.json')
            if (Test-Path $target) { continue }
            $record = @{
                id=$marker.BaseName;ok=$false;status='uncertain'
                error='Local in-flight journal found during supervised relay rebuild; no automatic replay'
            }
            $record | ConvertTo-Json -Compress |
                Set-Content -LiteralPath $target -Encoding UTF8
            $uncertain++
        }
    }
    # Preserve the previous checkout permanently; do not garbage-collect it.
    $success = $true
}
finally {
    if (!$success -and $switched -and (Test-Path $backup)) {
        $failedRepo = Join-Path $state ('private-bridge-repo-failed-' + $stamp)
        if (Test-Path $repo) { Move-Item -LiteralPath $repo -Destination $failedRepo }
        Move-Item -LiteralPath $backup -Destination $repo
    }
    Remove-Item -LiteralPath $guard -Force -ErrorAction SilentlyContinue
}
if (!$success) { throw 'Hard relay recovery failed; prior repository restored where possible' }

# Start ONE existing supervisor; the mutex prevents concurrent bridge workers.
Start-Process powershell.exe -ArgumentList @(
    '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
    ('"' + $launcher + '"')
) -WorkingDirectory $production -WindowStyle Hidden | Out-Null
Write-Output ('PRIVATE_RELAY_REBUILT; backup=' + $backup)
Write-Output ('OLD_RESULTS_PRESERVED=' + $recovered + '; UNCERTAIN_JOURNALS=' + $uncertain)
Start-Sleep -Seconds 10
if (Test-Path $healthPath) {
    $status = Get-Content $healthPath -Raw | ConvertFrom-Json
    Write-Output ('RELAY_PHASE=' + $status.phase + '; LAST_SYNC=' + $status.last_sync_utc)
    if ($status.phase -eq 'startup_error') {
        $failure = Join-Path $state 'control-git-bridge-startup-last-error.log'
        if (Test-Path $failure) {
            Get-Content $failure -Tail 24
        }
    }
}
