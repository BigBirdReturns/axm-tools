[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptRoot '..\..\..')).Path
$WorkflowPath = Join-Path $RepoRoot '.github\workflows\manzanita-v31-origin-host-recovery-execution-v1.yml'
$ExpectedPackageBytes = 553074
$ExpectedPackageSha256 = '2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738'
$ExpectedSourceReceiptName = 'V31_ORIGIN_HOST_RECOVERY_EXECUTION_SOURCE_VERIFICATION_RECEIPT_V1.json'
$Required = @(
  (Join-Path $ScriptRoot 'ORIGIN_HOST_EXECUTION_CONTRACT.json'),
  (Join-Path $ScriptRoot 'run_origin_host_recovery.ps1'),
  (Join-Path $ScriptRoot 'verify_origin_host_execution_source.ps1'),
  (Join-Path $ScriptRoot 'validate_origin_host_execution_summary.ps1'),
  (Join-Path $ScriptRoot 'README.md'),
  $WorkflowPath
)
$Checks = @()

function Add-Check([string]$Name, [bool]$Passed, $Observed) {
  $script:Checks += [ordered]@{ name = $Name; passed = $Passed; observed = $Observed }
  if (-not $Passed) { throw "source verification failed: $Name" }
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-AtomicJson([string]$Path, $Value) {
  $Parent = Split-Path -Parent $Path
  if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
  $Temporary = $Path + '.tmp-' + [Guid]::NewGuid().ToString('N')
  $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $Temporary -Encoding UTF8
  Move-Item -LiteralPath $Temporary -Destination $Path -Force
}

foreach ($Path in $Required) {
  Add-Check -Name ('required file: ' + [IO.Path]::GetFileName($Path)) -Passed (Test-Path -LiteralPath $Path -PathType Leaf) -Observed $Path
}

$ContractPath = Join-Path $ScriptRoot 'ORIGIN_HOST_EXECUTION_CONTRACT.json'
$Contract = Get-Content -LiteralPath $ContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$ExecutionPath = Join-Path $ScriptRoot 'run_origin_host_recovery.ps1'
$ValidationPath = Join-Path $ScriptRoot 'validate_origin_host_execution_summary.ps1'
$ExecutionText = Get-Content -LiteralPath $ExecutionPath -Raw -Encoding UTF8
$ValidationText = Get-Content -LiteralPath $ValidationPath -Raw -Encoding UTF8
$WorkflowText = Get-Content -LiteralPath $WorkflowPath -Raw -Encoding UTF8

Add-Check 'contract schema' ($Contract.schema -eq 'manzanita/v31-origin-host-recovery-execution-contract@1') $Contract.schema
Add-Check 'contract class' ($Contract.object_class -eq 'bounded self-hosted Windows recovery execution and exact-return collection') $Contract.object_class
Add-Check 'exact package name' ($Contract.source_package.filename -eq 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip') $Contract.source_package.filename
Add-Check 'exact package byte count' ($Contract.source_package.bytes -eq $ExpectedPackageBytes) $Contract.source_package.bytes
Add-Check 'exact package SHA-256' ($Contract.source_package.sha256 -eq $ExpectedPackageSha256) $Contract.source_package.sha256
Add-Check 'exact package release root' ($Contract.source_package.release_root -eq 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1') $Contract.source_package.release_root
Add-Check 'self-hosted Windows labels' ((@($Contract.workflow_scope.runner_labels) -join ',') -eq 'self-hosted,Windows') $Contract.workflow_scope.runner_labels
Add-Check 'pull request execution prohibited' ($Contract.workflow_scope.pull_request_trigger -eq $false -and $Contract.workflow_scope.fork_execution -eq $false) $Contract.workflow_scope
Add-Check 'privacy-bounded retention' ($Contract.workflow_scope.runner_name_retention -eq 'SHA-256 only' -and $Contract.workflow_scope.computer_name_retention -eq 'SHA-256 only' -and $Contract.workflow_scope.user_profile_retention -eq 'not retained' -and $Contract.workflow_scope.actions_artifact_retention_days -eq 1) $Contract.workflow_scope
Add-Check 'expected return name' ($Contract.expected_return.filename -eq 'MW_V31_OPERATOR_RETURN_COLLECTION_V3_R1.zip') $Contract.expected_return
Add-Check 'receiving intake remains separate' ($Contract.authority.receiving_intake_authority -eq $false -and $Contract.authority.production_admission_authority -eq $false -and $Contract.authority.accepted_parent_extraction_authority -eq $false -and $Contract.authority.inherited_baseline_replay_authority -eq $false) $Contract.authority
Add-Check 'product authority held' ($Contract.authority.v31_product_mutation_authority -eq $false -and $Contract.authority.operator_visual_acceptance -eq 'ABSENT') $Contract.authority
Add-Check 'merge and release authority held' ($Contract.authority.merge_authorized -eq $false -and $Contract.authority.release_authorized -eq $false) $Contract.authority
Add-Check 'public effects absent' ($Contract.authority.public_route_effect -eq 'none' -and $Contract.authority.pages_effect -eq 'none' -and $Contract.authority.external_effect -eq 'none') $Contract.authority

$Tokens = $null
$ParseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($ExecutionPath, [ref]$Tokens, [ref]$ParseErrors) | Out-Null
Add-Check 'execution PowerShell parses' ($ParseErrors.Count -eq 0) @($ParseErrors | ForEach-Object { $_.Message })
$Tokens = $null
$ParseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($ValidationPath, [ref]$Tokens, [ref]$ParseErrors) | Out-Null
Add-Check 'validation PowerShell parses' ($ParseErrors.Count -eq 0) @($ParseErrors | ForEach-Object { $_.Message })

Add-Check 'administrator context required' ($ExecutionText.Contains('Test-Administrator') -and $ExecutionText.Contains('Administrator context required for the complete recovery campaign')) $null
$ExpectedPackageAssignment = '$ExpectedPackageSha256 = ''' + $ExpectedPackageSha256 + ''''
Add-Check 'exact download gate present' ($ExecutionText.Contains('curl.exe -L --fail') -and $ExecutionText.Contains('$ExpectedPackageBytes = 553074') -and $ExecutionText.Contains($ExpectedPackageAssignment)) $null
Add-Check 'all package entrypoints bound' ((@('RUN_WINDOWS_PLATFORM_REPLAY.cmd','RUN_PREPARE_ONLY.cmd','RUN_ALL_RECOVERY_ADMIN.cmd','RUN_COLLECT_RETURNS.cmd') | ForEach-Object { $ExecutionText.Contains($_) } | Where-Object { -not $_ } | Measure-Object).Count -eq 0) $null
Add-Check 'lane logs redirected and summarized' ($ExecutionText.Contains('RedirectStandardOutput') -and $ExecutionText.Contains('RedirectStandardError') -and $ExecutionText.Contains('stdout_sha256') -and $ExecutionText.Contains('stderr_sha256')) $null
Add-Check 'raw host names not retained' ($ExecutionText.Contains('runner_name_sha256') -and $ExecutionText.Contains('computer_name_sha256') -and $ExecutionText.Contains('user_profile_retained = $false')) $null
Add-Check 'return collection independently inspected' ($ExecutionText.Contains('Inspect-ReturnCollection') -and $ExecutionText.Contains('paths_safe') -and $ExecutionText.Contains('paths_casefold_unique') -and $ExecutionText.Contains('manifest_present')) $null
Add-Check 'origin identity not overclaimed' ($ExecutionText.Contains('operator_origin_identity_proved = $false')) $null
Add-Check 'receiving and admission authority absent' ($ExecutionText.Contains('receiving_intake_invoked = $false') -and $ExecutionText.Contains('production_admission_invoked = $false') -and $ExecutionText.Contains('accepted_parent_extracted = $false')) $null
Add-Check 'product and release effects held' ($ExecutionText.Contains('v31_created = $false') -and $ExecutionText.Contains('product_files_modified = 0') -and $ExecutionText.Contains("operator_visual_acceptance = 'ABSENT'") -and $ExecutionText.Contains('merge_authorized = $false') -and $ExecutionText.Contains('release_authorized = $false')) $null

Add-Check 'workflow excludes pull request trigger' (-not [regex]::IsMatch($WorkflowText, '(?m)^\s*pull_request\s*:')) $null
Add-Check 'workflow has push trigger' ([regex]::IsMatch($WorkflowText, '(?m)^\s*push\s*:')) $null
Add-Check 'workflow branch is exact' ($WorkflowText.Contains('agent/manzanita-v31-origin-host-recovery-execution-v1')) $null
Add-Check 'workflow has manual dispatch' ([regex]::IsMatch($WorkflowText, '(?m)^\s*workflow_dispatch\s*:')) $null
Add-Check 'workflow uses self-hosted Windows' ($WorkflowText.Contains('runs-on: [self-hosted, Windows]')) $null
Add-Check 'workflow contents permission read only' ($WorkflowText.Contains('contents: read')) $null
Add-Check 'runner context excluded from job-level env' (-not [regex]::IsMatch($WorkflowText, '(?m)^    env:\s*$')) $null
Add-Check 'runner temporary paths assigned at step scope' ([regex]::Matches($WorkflowText, '(?m)^        env:\s*$').Count -eq 3 -and [regex]::Matches($WorkflowText, '\$\{\{\s*runner\.temp\s*\}\}').Count -eq 10) $null
Add-Check 'workflow artifact retention one day' ($WorkflowText.Contains('retention-days: 1')) $null
Add-Check 'workflow does not upload raw lane logs' (-not $WorkflowText.Contains('lane-logs') -and -not $WorkflowText.Contains('*.stdout.txt') -and -not $WorkflowText.Contains('*.stderr.txt')) $null
Add-Check 'workflow uploads only governed return and receipts' ($WorkflowText.Contains('V31_ORIGIN_HOST_RECOVERY_EXECUTION_RECEIPT_V1.json') -and $WorkflowText.Contains('V31_ORIGIN_HOST_RECOVERY_EXECUTION_RECEIPT_V1.validation.json') -and $WorkflowText.Contains('MW_V31_OPERATOR_RETURN_COLLECTION_V3_R1.zip') -and $WorkflowText.Contains($ExpectedSourceReceiptName)) $null

$Files = @()
foreach ($Path in $Required) {
  $Files += [ordered]@{
    path = $Path.Substring($RepoRoot.Length + 1).Replace('\\','/')
    bytes = (Get-Item -LiteralPath $Path).Length
    sha256 = Get-Sha256 $Path
  }
}

$Receipt = [ordered]@{
  schema = 'manzanita/v31-origin-host-recovery-execution-source-verification@1'
  result = 'PASS_V31_ORIGIN_HOST_RECOVERY_EXECUTION_SOURCE_VERIFIED'
  checks_passed = $Checks.Count
  checks_total = $Checks.Count
  checks = $Checks
  files = $Files
  authority = $Contract.authority
}
Write-AtomicJson -Path $OutputPath -Value $Receipt
Write-Host "PASS $($Checks.Count)/$($Checks.Count)"
