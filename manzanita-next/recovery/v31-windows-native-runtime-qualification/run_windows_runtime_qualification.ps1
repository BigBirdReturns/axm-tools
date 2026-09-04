[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ReceiptPath)

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ScriptRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'resolve_v31_python.ps1')
$started=[DateTimeOffset]::UtcNow.ToString('o')
$work=Join-Path $env:RUNNER_TEMP ('v31-windows-runtime-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work -Force | Out-Null
$receipt=[ordered]@{
  schema='manzanita/v31-windows-native-runtime-qualification-receipt@1'
  result='FAIL_WINDOWS_NATIVE_RUNTIME_QUALIFICATION_NOT_COMPLETED'
  started_at=$started
  completed_at=$null
  environment=[ordered]@{
    os=[Environment]::OSVersion.VersionString
    powershell_edition=$PSVersionTable.PSEdition
    powershell_version=$PSVersionTable.PSVersion.ToString()
    runner_temp=$env:RUNNER_TEMP
  }
  broken_candidate_probe=$null
  runtime=$null
  shims=$null
  alias_observations=@()
  checks=@()
  authority=[ordered]@{
    product_files_modified=0
    operator_host_execution_proved=$false
    production_inputs_materialized=0
    admission_invoked=$false
    v31_created=$false
    merge_authorized=$false
    release_authorized=$false
    public_route_effect='none'
    pages_effect='none'
    external_effect='none'
  }
  error=$null
}
function Add-Check([string]$Name,[bool]$Passed,[object]$Observed){
  $script:receipt.checks+=,[ordered]@{name=$Name;passed=$Passed;observed=$Observed}
  if(-not $Passed){throw "qualification check failed: $Name"}
}
try{
  $fakeDir=Join-Path $work 'broken-candidate'
  New-Item -ItemType Directory -Path $fakeDir -Force | Out-Null
  $fake=Join-Path $fakeDir 'python.exe'
  Copy-Item -LiteralPath (Join-Path $env:WINDIR 'System32\cmd.exe') -Destination $fake -Force
  $broken=Invoke-V31PythonProbe -Path $fake -Prefix @() -MinimumMajor 3 -MinimumMinor 10
  $receipt.broken_candidate_probe=$broken
  Add-Check 'broken executable candidate is refused' (-not $broken.probe_passed) $broken

  $runtime=Resolve-V31Python -MinimumMajor 3 -MinimumMinor 10
  $receipt.runtime=$runtime
  Add-Check 'supported Python runtime resolves' ($runtime.result -eq 'PASS_SUPPORTED_PYTHON_RUNTIME_RESOLVED') $runtime.result
  Add-Check 'resolved runtime meets version floor' ([int]$runtime.selected.version[0] -gt 3 -or ([int]$runtime.selected.version[0] -eq 3 -and [int]$runtime.selected.version[1] -ge 10)) $runtime.selected.version

  $shimRoot=Join-Path $work 'python-shims'
  $shims=Install-V31PythonShims -Runtime $runtime -ShimRoot $shimRoot
  $receipt.shims=$shims
  Add-Check 'three process-local aliases installed' ((@($shims.aliases).Count -eq 3) -and (Test-Path (Join-Path $shimRoot 'py.cmd')) -and (Test-Path (Join-Path $shimRoot 'python.cmd')) -and (Test-Path (Join-Path $shimRoot 'python3.cmd'))) $shims.aliases

  $probeScript=Join-Path $work 'alias_probe.py'
  [IO.File]::WriteAllText($probeScript,"import json,sys`nprint(json.dumps({'version': list(sys.version_info[:3]), 'executable': sys.executable}))`n",[Text.Encoding]::UTF8)
  $aliases=@(
    @{name='py';cmd=(Join-Path $shimRoot 'py.cmd');args=@('-3','-I','-B',$probeScript)},
    @{name='python';cmd=(Join-Path $shimRoot 'python.cmd');args=@('-I','-B',$probeScript)},
    @{name='python3';cmd=(Join-Path $shimRoot 'python3.cmd');args=@('-I','-B',$probeScript)}
  )
  foreach($alias in $aliases){
    $output=& $alias.cmd @($alias.args) 2>&1
    $rc=$LASTEXITCODE
    $parsed=$null
    if($rc -eq 0){$parsed=($output | Select-Object -Last 1 | ConvertFrom-Json)}
    $observation=[ordered]@{alias=$alias.name;exit_code=$rc;output=@($output);parsed=$parsed}
    $receipt.alias_observations+=,$observation
    Add-Check ("alias executes: "+$alias.name) ($rc -eq 0 -and $null -ne $parsed) $observation
    Add-Check ("alias executable continuity: "+$alias.name) ([IO.Path]::GetFullPath([string]$parsed.executable).ToLowerInvariant() -eq [IO.Path]::GetFullPath([string]$runtime.selected.executable).ToLowerInvariant()) ([ordered]@{alias=$parsed.executable;selected=$runtime.selected.executable})
  }
  Add-Check 'PATH modification remains process-local' ($env:PATH.StartsWith($shimRoot+';',[StringComparison]::OrdinalIgnoreCase)) $env:PATH.Substring(0,[Math]::Min($env:PATH.Length,$shimRoot.Length+1))
  Add-Check 'authority remains held' ($receipt.authority.product_files_modified -eq 0 -and -not $receipt.authority.operator_host_execution_proved -and $receipt.authority.production_inputs_materialized -eq 0 -and -not $receipt.authority.admission_invoked -and -not $receipt.authority.v31_created -and -not $receipt.authority.merge_authorized -and -not $receipt.authority.release_authorized -and $receipt.authority.public_route_effect -eq 'none' -and $receipt.authority.pages_effect -eq 'none' -and $receipt.authority.external_effect -eq 'none') $receipt.authority
  $receipt.result='PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED'
}catch{
  $receipt.error=$_.Exception.Message
}
$receipt.completed_at=[DateTimeOffset]::UtcNow.ToString('o')
$parent=Split-Path -Parent $ReceiptPath
if($parent){New-Item -ItemType Directory -Path $parent -Force | Out-Null}
$tmp=$ReceiptPath+'.tmp-'+[Guid]::NewGuid().ToString('N')
$receipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $tmp -Encoding UTF8
Move-Item -LiteralPath $tmp -Destination $ReceiptPath -Force
Write-Host "Receipt: $ReceiptPath"
Write-Host "Result: $($receipt.result)"
if($receipt.result -ne 'PASS_WINDOWS_NATIVE_RUNTIME_RESOLVER_AND_SHIMS_QUALIFIED'){exit 3}
exit 0
