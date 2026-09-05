[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$SummaryPath,
  [Parameter(Mandatory=$true)][string]$ReturnPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ExpectedPackageSha256 = '2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738'
$ExpectedPackageBytes = 553074
$ExpectedReturnName = 'MW_V31_OPERATOR_RETURN_COLLECTION_V3_R1.zip'
$ExpectedPlatformPass = 'PASS_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY'
$AcceptedResults = @(
  'PASS_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTED_CANDIDATE_RETURN_PRESENT_RECEIVING_INTAKE_REQUIRED',
  'HOLD_SELF_HOSTED_WINDOWS_RECOVERY_EXECUTED_COMPLETE_PRODUCTION_SET_NOT_RETURNED'
)
$Checks = @()

function Add-Check([string]$Name, [bool]$Passed, $Observed) {
  $script:Checks += [ordered]@{ name = $Name; passed = $Passed; observed = $Observed }
  if (-not $Passed) { throw "summary validation failed: $Name" }
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-HexSha256($Value) {
  return ($Value -is [string]) -and ($Value -match '^[0-9a-f]{64}$')
}

function Write-AtomicJson([string]$Path, $Value) {
  $Parent = Split-Path -Parent $Path
  if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
  $Temporary = $Path + '.tmp-' + [Guid]::NewGuid().ToString('N')
  $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $Temporary -Encoding UTF8
  Move-Item -LiteralPath $Temporary -Destination $Path -Force
}

function Inspect-ReturnCollection([string]$Path) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $Archive = [IO.Compression.ZipFile]::OpenRead($Path)
  try {
    $Names = @()
    $Folded = @{}
    $Unsafe = @()
    $Duplicates = @()
    $Total = [Int64]0
    $Manifest = $null
    foreach ($Entry in $Archive.Entries) {
      $Name = $Entry.FullName.Replace('\\','/')
      $Names += $Name
      $Total += $Entry.Length
      $Parts = @($Name.Split('/'))
      if ([string]::IsNullOrWhiteSpace($Name) -or $Name.StartsWith('/') -or $Name.StartsWith('\\') -or $Name -match '^[A-Za-z]:' -or $Parts -contains '..' -or $Parts -contains '.') {
        $Unsafe += $Name
      }
      $Key = $Name.ToLowerInvariant()
      if ($Folded.ContainsKey($Key)) { $Duplicates += $Name } else { $Folded[$Key] = $true }
      if ($Name -eq 'COLLECTION_MANIFEST.json') {
        $Reader = [IO.StreamReader]::new($Entry.Open(), [Text.Encoding]::UTF8)
        try { $Manifest = $Reader.ReadToEnd() | ConvertFrom-Json } finally { $Reader.Dispose() }
      }
    }
    return [ordered]@{
      name = [IO.Path]::GetFileName($Path)
      bytes = (Get-Item -LiteralPath $Path).Length
      sha256 = Get-Sha256 $Path
      members = $Archive.Entries.Count
      uncompressed_bytes = $Total
      paths_safe = ($Unsafe.Count -eq 0)
      path_violations = @($Unsafe)
      paths_casefold_unique = ($Duplicates.Count -eq 0)
      duplicate_or_case_colliding = @($Duplicates)
      manifest_present = ($null -ne $Manifest)
      manifest = $Manifest
    }
  } finally {
    $Archive.Dispose()
  }
}

if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
  throw "summary absent: $SummaryPath"
}
if (-not (Test-Path -LiteralPath $ReturnPath -PathType Leaf)) {
  throw "return collection absent: $ReturnPath"
}

$Summary = Get-Content -LiteralPath $SummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Return = Inspect-ReturnCollection -Path $ReturnPath

Add-Check 'summary schema' ($Summary.schema -eq 'manzanita/v31-origin-host-recovery-execution-receipt@1') $Summary.schema
Add-Check 'execution result classified' ($AcceptedResults -contains $Summary.result) $Summary.result
Add-Check 'execution observed' ($Summary.standing.execution_observed -eq $true) $Summary.standing.execution_observed
Add-Check 'Windows self-hosted seat observed' ($Summary.host.windows -eq $true -and $Summary.host.host_class -eq 'self-hosted Windows recovery seat') $Summary.host
Add-Check 'administrator context observed' ($Summary.host.administrator -eq $true) $Summary.host.administrator
Add-Check 'runner identity hashed' (Test-HexSha256 $Summary.host.runner_name_sha256) $Summary.host.runner_name_sha256
Add-Check 'computer identity hashed' (Test-HexSha256 $Summary.host.computer_name_sha256) $Summary.host.computer_name_sha256
Add-Check 'user profile not retained' ($Summary.host.user_profile_retained -eq $false) $Summary.host.user_profile_retained
Add-Check 'origin identity not overclaimed' ($Summary.standing.operator_origin_identity_proved -eq $false) $Summary.standing.operator_origin_identity_proved

Add-Check 'exact package admitted' ($Summary.exact_package.admitted -eq $true) $Summary.exact_package
Add-Check 'exact package byte count' ($Summary.exact_package.observed_bytes -eq $ExpectedPackageBytes -and $Summary.exact_package.expected_bytes -eq $ExpectedPackageBytes) $Summary.exact_package
Add-Check 'exact package SHA-256' ($Summary.exact_package.observed_sha256 -eq $ExpectedPackageSha256 -and $Summary.exact_package.expected_sha256 -eq $ExpectedPackageSha256) $Summary.exact_package

$Lanes = @($Summary.lanes)
$LaneNames = @($Lanes | ForEach-Object { $_.name })
Add-Check 'four bounded lanes recorded' ($Lanes.Count -eq 4) $LaneNames
Add-Check 'platform replay lane recorded' ($LaneNames -contains 'platform_replay') $LaneNames
Add-Check 'prepare lane recorded' ($LaneNames -contains 'prepare') $LaneNames
Add-Check 'recovery lane recorded' ($LaneNames -contains 'recovery') $LaneNames
Add-Check 'collect lane recorded' ($LaneNames -contains 'collect') $LaneNames
foreach ($Lane in $Lanes) {
  Add-Check ("lane timing recorded: " + $Lane.name) (($Lane.duration_seconds -as [double]) -ge 0 -and $Lane.started_at -and $Lane.completed_at) $Lane
  Add-Check ("lane log digests recorded: " + $Lane.name) (Test-HexSha256 $Lane.stdout_sha256 -and Test-HexSha256 $Lane.stderr_sha256) $Lane
}
$PlatformLane = @($Lanes | Where-Object { $_.name -eq 'platform_replay' })[0]
$PrepareLane = @($Lanes | Where-Object { $_.name -eq 'prepare' })[0]
$CollectLane = @($Lanes | Where-Object { $_.name -eq 'collect' })[0]
Add-Check 'platform replay exited zero' ($PlatformLane.exit_code -eq 0) $PlatformLane.exit_code
Add-Check 'prepare exited zero' ($PrepareLane.exit_code -eq 0) $PrepareLane.exit_code
Add-Check 'collect exited zero' ($CollectLane.exit_code -eq 0) $CollectLane.exit_code

$Receipts = @($Summary.receipts)
$PlatformReceipts = @($Receipts | Where-Object { $_.name -eq 'V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1_WINDOWS_PLATFORM_REPLAY_RECEIPT.json' })
Add-Check 'package-owned platform receipt unique' ($PlatformReceipts.Count -eq 1) @($PlatformReceipts | ForEach-Object { $_.name })
Add-Check 'package-owned platform receipt PASS' ($PlatformReceipts[0].result -eq $ExpectedPlatformPass) $PlatformReceipts[0]
Add-Check 'receipt inventory contains machine objects' ($Receipts.Count -gt 0) $Receipts.Count
foreach ($Receipt in $Receipts) {
  Add-Check ("receipt identity complete: " + $Receipt.name) (($Receipt.bytes -as [long]) -ge 0 -and (Test-HexSha256 $Receipt.sha256) -and $Receipt.name -match '\.json$') $Receipt
}

Add-Check 'return collection expected filename' ($Return.name -eq $ExpectedReturnName) $Return.name
Add-Check 'return collection nonempty' ($Return.bytes -gt 0 -and $Return.members -gt 0) $Return
Add-Check 'return collection safe paths' ($Return.paths_safe -eq $true) $Return.path_violations
Add-Check 'return collection casefold unique' ($Return.paths_casefold_unique -eq $true) $Return.duplicate_or_case_colliding
Add-Check 'return collection manifest present' ($Return.manifest_present -eq $true) $Return
Add-Check 'return collection manifest result' ($Return.manifest.result -eq 'PASS_DETERMINISTIC_OPERATOR_RETURN_COLLECTION_BUILT') $Return.manifest.result
Add-Check 'summary return byte count matches' ($Summary.return_collection.bytes -eq $Return.bytes) @{ summary = $Summary.return_collection.bytes; observed = $Return.bytes }
Add-Check 'summary return SHA-256 matches' ($Summary.return_collection.sha256 -eq $Return.sha256) @{ summary = $Summary.return_collection.sha256; observed = $Return.sha256 }
Add-Check 'summary return membership matches' ($Summary.return_collection.members -eq $Return.members) @{ summary = $Summary.return_collection.members; observed = $Return.members }
Add-Check 'return remains receiving-intake candidate' ($Summary.return_collection.production_standing -eq 'NONE_RECEIVING_INTAKE_REQUIRED') $Summary.return_collection.production_standing

Add-Check 'receiving intake not invoked' ($Summary.standing.receiving_intake_invoked -eq $false) $Summary.standing.receiving_intake_invoked
Add-Check 'production inputs remain zero' ($Summary.standing.production_inputs_materialized -eq 0) $Summary.standing.production_inputs_materialized
Add-Check 'production admission not invoked' ($Summary.standing.production_admission_invoked -eq $false) $Summary.standing.production_admission_invoked
Add-Check 'accepted parent not extracted' ($Summary.standing.accepted_parent_extracted -eq $false) $Summary.standing.accepted_parent_extracted
Add-Check 'inherited replay unauthorized' ($Summary.standing.inherited_baseline_replay_authorized -eq $false) $Summary.standing.inherited_baseline_replay_authorized
Add-Check 'v31 not created' ($Summary.standing.v31_created -eq $false) $Summary.standing.v31_created
Add-Check 'product files unmodified' ($Summary.standing.product_files_modified -eq 0) $Summary.standing.product_files_modified
Add-Check 'operator visual acceptance absent' ($Summary.standing.operator_visual_acceptance -eq 'ABSENT') $Summary.standing.operator_visual_acceptance
Add-Check 'merge and release authority held' ($Summary.standing.merge_authorized -eq $false -and $Summary.standing.release_authorized -eq $false) $Summary.standing
Add-Check 'public effects absent' ($Summary.standing.public_route_effect -eq 'none' -and $Summary.standing.pages_effect -eq 'none' -and $Summary.standing.external_effect -eq 'none') $Summary.standing

$Output = [ordered]@{
  schema = 'manzanita/v31-origin-host-recovery-execution-validation@1'
  result = 'PASS_V31_ORIGIN_HOST_RECOVERY_EXECUTION_SUMMARY_AND_RETURN_VALIDATED'
  checks_passed = $Checks.Count
  checks_total = $Checks.Count
  checks = $Checks
  summary = [ordered]@{
    path = $SummaryPath
    bytes = (Get-Item -LiteralPath $SummaryPath).Length
    sha256 = Get-Sha256 $SummaryPath
    result = $Summary.result
  }
  return_collection = $Return
  standing = [ordered]@{
    self_hosted_windows_recovery_execution = 'OBSERVED'
    operator_origin_identity = 'NOT_PROVED'
    receiving_intake = 'REQUIRED'
    production_inputs_materialized = 0
    production_admission = 'NOT_INVOKED'
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
}
Write-AtomicJson -Path $OutputPath -Value $Output
Write-Host "PASS $($Checks.Count)/$($Checks.Count)"
