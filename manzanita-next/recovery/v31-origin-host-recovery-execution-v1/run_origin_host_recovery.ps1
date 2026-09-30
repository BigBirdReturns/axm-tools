[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$SummaryPath,
  [Parameter(Mandatory=$true)][string]$ReturnPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedPackageName = 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip'
$ExpectedPackageBytes = 553074
$ExpectedPackageSha256 = '2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738'
$ExpectedReturnName = 'MW_V31_OPERATOR_RETURN_COLLECTION_V3_R1.zip'
$DownloadUrl = 'https://drive.usercontent.google.com/download?id=1tX9hAVhNdThVUq6ozuIfrqn5vAhgSxU3&export=download&confirm=t'
$ExpectedRoot = 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1'
$ExpectedPlatformPass = 'PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY'

function Get-UtcIso {
  return [DateTimeOffset]::UtcNow.ToString('o')
}

function Get-TextSha256([string]$Value) {
  $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Write-AtomicJson([string]$Path, $Value) {
  $parent = Split-Path -Parent $Path
  if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $temp = $Path + '.tmp-' + [Guid]::NewGuid().ToString('N')
  $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $temp -Encoding UTF8
  Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Test-Administrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-BoundedLane {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Launcher,
    [Parameter(Mandatory=$true)][string]$LogRoot
  )
  $started = [DateTimeOffset]::UtcNow
  $stdout = Join-Path $LogRoot ($Name + '.stdout.txt')
  $stderr = Join-Path $LogRoot ($Name + '.stderr.txt')
  $command = 'call "' + $Launcher + '"'
  $process = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/s', '/c', $command) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $completed = [DateTimeOffset]::UtcNow
  return [ordered]@{
    name = $Name
    launcher = [IO.Path]::GetFileName($Launcher)
    started_at = $started.ToString('o')
    completed_at = $completed.ToString('o')
    duration_seconds = [Math]::Round(($completed - $started).TotalSeconds, 3)
    exit_code = $process.ExitCode
    stdout_bytes = if (Test-Path -LiteralPath $stdout) { (Get-Item -LiteralPath $stdout).Length } else { 0 }
    stderr_bytes = if (Test-Path -LiteralPath $stderr) { (Get-Item -LiteralPath $stderr).Length } else { 0 }
    stdout_sha256 = if (Test-Path -LiteralPath $stdout) { (Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    stderr_sha256 = if (Test-Path -LiteralPath $stderr) { (Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
  }
}

function Get-ReceiptInventory([string]$Workspace) {
  $rows = @()
  $evidence = Join-Path $Workspace 'evidence'
  if (-not (Test-Path -LiteralPath $evidence -PathType Container)) { return $rows }
  foreach ($file in @(Get-ChildItem -LiteralPath $evidence -Filter '*.json' -File -ErrorAction SilentlyContinue | Sort-Object Name)) {
    $result = $null
    $schema = $null
    $checksPassed = $null
    $checksTotal = $null
    try {
      $obj = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
      $result = $obj.result
      $schema = $obj.schema
      $checksPassed = $obj.checks_passed
      $checksTotal = $obj.checks_total
    } catch {
      $result = 'UNPARSEABLE_JSON'
    }
    $rows += [ordered]@{
      name = $file.Name
      bytes = $file.Length
      sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
      schema = $schema
      result = $result
      checks_passed = $checksPassed
      checks_total = $checksTotal
    }
  }
  return $rows
}

function Inspect-ReturnCollection([string]$Path) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [IO.Compression.ZipFile]::OpenRead($Path)
  try {
    $names = @()
    $folded = @{}
    $unsafe = @()
    $duplicates = @()
    $total = [Int64]0
    $manifest = $null
    foreach ($entry in $archive.Entries) {
      $name = $entry.FullName.Replace('\', '/')
      $names += $name
      $total += $entry.Length
      if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or $name.StartsWith('\') -or $name.Contains('../') -or $name.Contains('/./') -or $name -match '^[A-Za-z]:') {
        $unsafe += $name
      }
      $key = $name.ToLowerInvariant()
      if ($folded.ContainsKey($key)) { $duplicates += $name } else { $folded[$key] = $true }
      if ($name -eq 'COLLECTION_MANIFEST.json') {
        $reader = [IO.StreamReader]::new($entry.Open(), [Text.Encoding]::UTF8)
        try { $manifest = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
      }
    }
    $selected = @()
    $candidates = @()
    $prior = @()
    if ($null -ne $manifest) {
      if ($null -ne $manifest.selected) { $selected = @($manifest.selected) }
      if ($null -ne $manifest.public_convergence_candidates) { $candidates = @($manifest.public_convergence_candidates) }
      if ($null -ne $manifest.prior_envelopes) { $prior = @($manifest.prior_envelopes) }
    }
    return [ordered]@{
      name = [IO.Path]::GetFileName($Path)
      bytes = (Get-Item -LiteralPath $Path).Length
      sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
      members = $archive.Entries.Count
      uncompressed_bytes = $total
      paths_safe = ($unsafe.Count -eq 0)
      path_violations = @($unsafe)
      paths_casefold_unique = ($duplicates.Count -eq 0)
      duplicate_or_case_colliding = @($duplicates)
      manifest_present = ($null -ne $manifest)
      manifest_result = if ($null -ne $manifest) { $manifest.result } else { $null }
      selected_count = $selected.Count
      selected_keys = @($selected | ForEach-Object { $_.key } | Where-Object { $_ } | Sort-Object -Unique)
      public_convergence_candidate_count = $candidates.Count
      prior_envelope_count = $prior.Count
      production_standing = 'NONE_RECEIVING_INTAKE_REQUIRED'
    }
  } finally {
    $archive.Dispose()
  }
}

$startedAt = Get-UtcIso
$summary = [ordered]@{
  schema = 'manzanita/v31-origin-host-recovery-execution-receipt@1'
  result = 'FAIL_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTION_NOT_COMPLETED'
  started_at = $startedAt
  completed_at = $null
  host = [ordered]@{
    host_class = 'self-hosted Windows recovery seat'
    windows = ($env:OS -eq 'Windows_NT')
    administrator = $false
    runner_name_sha256 = if ($env:RUNNER_NAME) { Get-TextSha256 $env:RUNNER_NAME } else { $null }
    computer_name_sha256 = if ($env:COMPUTERNAME) { Get-TextSha256 $env:COMPUTERNAME } else { $null }
    runner_environment = $env:RUNNER_ENVIRONMENT
    architecture = $env:PROCESSOR_ARCHITECTURE
    user_profile_retained = $false
  }
  exact_package = [ordered]@{
    name = $ExpectedPackageName
    expected_bytes = $ExpectedPackageBytes
    expected_sha256 = $ExpectedPackageSha256
    observed_bytes = $null
    observed_sha256 = $null
    admitted = $false
  }
  lanes = @()
  receipts = @()
  return_collection = $null
  blockers = @()
  standing = [ordered]@{
    execution_observed = $false
    operator_origin_identity_proved = $false
    production_inputs_materialized = 0
    receiving_intake_invoked = $false
    production_admission_invoked = $false
    accepted_parent_extracted = $false
    inherited_baseline_replay_authorized = $false
    v31_created = $false
    product_files_modified = 0
    operator_visual_acceptance = 'ABSENT'
    merge_authorized = $false
    release_authorized = $false
    public_route_effect = 'none'
    pages_effect = 'none'
    external_effect = 'none'
  }
  error = $null
}

try {
  if ($env:OS -ne 'Windows_NT') { throw 'Windows host required' }
  $summary.host.administrator = Test-Administrator
  if (-not $summary.host.administrator) {
    $summary.result = 'HOLD_SELF_HOSTED_WINDOWS_RECOVERY_SEAT_NOT_ELEVATED'
    $summary.blockers += 'administrator context absent; raw-device and protected-profile recovery not authorized'
    throw 'Administrator context required for the complete recovery campaign'
  }

  $workRoot = Join-Path $env:RUNNER_TEMP 'v31-origin-host-recovery-execution-v1'
  if (Test-Path -LiteralPath $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force }
  New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
  $logRoot = Join-Path $workRoot 'lane-logs'
  New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
  $packagePath = Join-Path $workRoot $ExpectedPackageName
  $extractRoot = Join-Path $workRoot 'exact-package'
  $workspace = Join-Path $env:RUNNER_TEMP 'v31-origin-host-workspace-v3-r1'
  if (Test-Path -LiteralPath $workspace) { Remove-Item -LiteralPath $workspace -Recurse -Force }
  New-Item -ItemType Directory -Path $workspace -Force | Out-Null
  $env:V31_OPERATOR_WORKSPACE = $workspace
  $env:PYTHONDONTWRITEBYTECODE = '1'

  & curl.exe -L --fail --silent --show-error --retry 3 --retry-delay 2 --output $packagePath $DownloadUrl
  if ($LASTEXITCODE -ne 0) { throw "exact package download failed with exit code $LASTEXITCODE" }
  $summary.exact_package.observed_bytes = (Get-Item -LiteralPath $packagePath).Length
  $summary.exact_package.observed_sha256 = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($summary.exact_package.observed_bytes -ne $ExpectedPackageBytes) { throw 'exact package byte count mismatch' }
  if ($summary.exact_package.observed_sha256 -ne $ExpectedPackageSha256) { throw 'exact package SHA-256 mismatch' }
  $summary.exact_package.admitted = $true

  Expand-Archive -LiteralPath $packagePath -DestinationPath $extractRoot -Force
  $packageRoot = Join-Path $extractRoot $ExpectedRoot
  if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) { throw 'exact package root absent after extraction' }

  $entrypoints = [ordered]@{
    platform_replay = Join-Path $packageRoot 'RUN_WINDOWS_PLATFORM_REPLAY.cmd'
    prepare = Join-Path $packageRoot 'RUN_PREPARE_ONLY.cmd'
    recovery = Join-Path $packageRoot 'RUN_ALL_RECOVERY_ADMIN.cmd'
    collect = Join-Path $packageRoot 'RUN_COLLECT_RETURNS.cmd'
  }
  foreach ($name in $entrypoints.Keys) {
    if (-not (Test-Path -LiteralPath $entrypoints[$name] -PathType Leaf)) { throw "missing package entrypoint: $name" }
  }

  foreach ($name in @('platform_replay', 'prepare', 'recovery', 'collect')) {
    $lane = Invoke-BoundedLane -Name $name -Launcher $entrypoints[$name] -LogRoot $logRoot
    $summary.lanes += $lane
  }

  $platform = @($summary.lanes | Where-Object { $_.name -eq 'platform_replay' })[0]
  $collect = @($summary.lanes | Where-Object { $_.name -eq 'collect' })[0]
  if ($platform.exit_code -ne 0) { $summary.blockers += "package-owned platform replay exit code $($platform.exit_code)" }
  if ($collect.exit_code -ne 0) { $summary.blockers += "deterministic return collection exit code $($collect.exit_code)" }

  $summary.receipts = @(Get-ReceiptInventory -Workspace $workspace)
  $platformReceipt = @($summary.receipts | Where-Object { $_.name -eq 'V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY_RECEIPT.json' })
  if ($platformReceipt.Count -ne 1 -or $platformReceipt[0].result -ne $ExpectedPlatformPass) {
    $summary.blockers += 'package-owned Windows platform replay PASS receipt absent'
  }

  $collection = Join-Path $workspace $ExpectedReturnName
  if (Test-Path -LiteralPath $collection -PathType Leaf) {
    $summary.return_collection = Inspect-ReturnCollection -Path $collection
    $returnParent = Split-Path -Parent $ReturnPath
    if ($returnParent) { New-Item -ItemType Directory -Path $returnParent -Force | Out-Null }
    Copy-Item -LiteralPath $collection -Destination $ReturnPath -Force
  } else {
    $summary.blockers += 'package-governed deterministic return collection absent'
  }

  $summary.standing.execution_observed = $true
  if ($summary.return_collection -and $summary.return_collection.paths_safe -and $summary.return_collection.paths_casefold_unique -and $summary.return_collection.manifest_present) {
    if ($summary.return_collection.selected_count -gt 0 -or $summary.return_collection.public_convergence_candidate_count -gt 0 -or $summary.return_collection.prior_envelope_count -gt 0) {
      $summary.result = 'PASS_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTED_CANDIDATE_RETURN_PRESENT_RECEIVING_INTAKE_REQUIRED'
    } else {
      $summary.result = 'HOLD_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTED_COMPLETE_PRODUCTION_SET_NOT_RETURNED'
    }
  } else {
    $summary.result = 'HOLD_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTED_RETURN_COLLECTION_INCOMPLETE_OR_ABSENT'
  }
} catch {
  if ($summary.result -eq 'FAIL_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTION_NOT_COMPLETED') {
    $summary.result = 'FAIL_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTION_ABORTED'
  }
  $summary.error = $_.Exception.Message
} finally {
  $summary.completed_at = Get-UtcIso
  Write-AtomicJson -Path $SummaryPath -Value $summary
}

Write-Host "Result: $($summary.result)"
Write-Host "Summary: $SummaryPath"
if ($summary.return_collection) { Write-Host "Return collection: $ReturnPath" }

if (-not $summary.standing.execution_observed) { exit 3 }
if (-not $summary.exact_package.admitted) { exit 4 }
if (-not $summary.return_collection) { exit 5 }
exit 0
