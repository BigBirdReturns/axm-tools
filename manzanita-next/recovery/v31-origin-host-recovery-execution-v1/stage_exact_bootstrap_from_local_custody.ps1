[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [Parameter(Mandatory=$true)][string]$ReceiptPath,
  [int]$MaximumDirectoriesPerRoot = 5000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ExpectedName = 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1.zip'
$ExpectedBytes = 553074
$ExpectedSha256 = '2c4437c2f3c0cd7599b790ddc1a31315751db751daa3a81e4245e2a32b5f3738'
$ExpectedRoot = 'MW_V31_OPERATOR_EXECUTION_BOOTSTRAP_V3_R1'
$RequiredMembers = @(
  "$ExpectedRoot/RUN_WINDOWS_PLATFORM_REPLAY.cmd",
  "$ExpectedRoot/RUN_PREPARE_ONLY.cmd",
  "$ExpectedRoot/RUN_ALL_RECOVERY_ADMIN.cmd",
  "$ExpectedRoot/RUN_COLLECT_RETURNS.cmd",
  "$ExpectedRoot/START_HERE.txt",
  "$ExpectedRoot/SOURCE_MANIFEST.json"
)

function Get-UtcIso { return [DateTimeOffset]::UtcNow.ToString('o') }
function Get-Sha256([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-Utf8NoBom([string]$Path, [string]$Text) {
  $Parent = Split-Path -Parent $Path
  if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
  [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}
function Write-Receipt($Value) {
  Write-Utf8NoBom -Path $ReceiptPath -Text (($Value | ConvertTo-Json -Depth 40) + "`n")
}
function Test-ReparsePoint([IO.FileSystemInfo]$Item) {
  return (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
}
function Test-UnsafeZipName([string]$Name) {
  if ([string]::IsNullOrWhiteSpace($Name) -or $Name.Contains('\') -or $Name.StartsWith('/') -or $Name -match '^[A-Za-z]:') { return $true }
  $Parts = @($Name.Split('/'))
  return ($Parts -contains '..' -or $Parts -contains '.' -or $Parts -contains '')
}
function Test-ExactArchive([string]$Path) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $Archive = [IO.Compression.ZipFile]::OpenRead($Path)
  try {
    $Folded = @{}
    $Roots = @{}
    $Names = @()
    $Unsafe = @()
    $Symlinks = @()
    foreach ($Entry in $Archive.Entries) {
      $Name = $Entry.FullName
      $Names += $Name
      if (Test-UnsafeZipName $Name) { $Unsafe += $Name }
      $Key = $Name.ToLowerInvariant()
      if ($Folded.ContainsKey($Key)) { throw "duplicate or case-colliding ZIP member: $Name" }
      $Folded[$Key] = $true
      $Root = $Name.Split('/')[0]
      if ($Root) { $Roots[$Root] = $true }
      $UnixType = (($Entry.ExternalAttributes -shr 16) -band 0xF000)
      if ($UnixType -eq 0xA000) { $Symlinks += $Name }
      if (-not $Entry.FullName.EndsWith('/')) {
        $Stream = $Entry.Open()
        try {
          $Buffer = New-Object byte[] 1048576
          while ($Stream.Read($Buffer, 0, $Buffer.Length) -gt 0) { }
        } finally { $Stream.Dispose() }
      }
    }
    if ($Unsafe.Count -gt 0) { throw 'unsafe ZIP member path detected' }
    if ($Symlinks.Count -gt 0) { throw 'symbolic-link ZIP member detected' }
    if ($Roots.Keys.Count -ne 1 -or -not $Roots.ContainsKey($ExpectedRoot)) { throw 'expected single ZIP root absent' }
    foreach ($Required in $RequiredMembers) {
      if (-not $Folded.ContainsKey($Required.ToLowerInvariant())) { throw "required ZIP member absent: $Required" }
    }
    return [ordered]@{
      members = $Archive.Entries.Count
      paths_safe = $true
      names_casefold_unique = $true
      symbolic_links_absent = $true
      exact_single_root = $true
      required_members_present = $true
    }
  } finally { $Archive.Dispose() }
}
function Add-SearchRoot([Collections.Generic.List[object]]$Rows, [string]$Class, [string]$Path, [int]$Depth) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  $Rows.Add([pscustomobject]@{ source_class = $Class; path = $Path; maximum_depth = $Depth }) | Out-Null
}
function Find-Candidates([string]$Root, [int]$MaximumDepth, [int]$MaximumDirectories) {
  $Found = [Collections.Generic.List[string]]::new()
  if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return [ordered]@{ files = @(); directories = 0; capped = $false } }
  $Queue = [Collections.Generic.Queue[object]]::new()
  $Queue.Enqueue([pscustomobject]@{ path = $Root; depth = 0 })
  $Seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  $Directories = 0
  $Capped = $false
  while ($Queue.Count -gt 0) {
    $Node = $Queue.Dequeue()
    if ($Directories -ge $MaximumDirectories) { $Capped = $true; break }
    try { $Resolved = [IO.Path]::GetFullPath($Node.path) } catch { continue }
    if (-not $Seen.Add($Resolved)) { continue }
    $Directories++
    try { $Children = @(Get-ChildItem -LiteralPath $Resolved -Force -ErrorAction Stop) } catch { continue }
    foreach ($Child in $Children) {
      if (Test-ReparsePoint $Child) { continue }
      if ($Child.PSIsContainer) {
        if ($Node.depth -lt $MaximumDepth) { $Queue.Enqueue([pscustomobject]@{ path = $Child.FullName; depth = $Node.depth + 1 }) }
      } elseif ($Child.Name -eq $ExpectedName) {
        $Found.Add($Child.FullName)
      }
    }
  }
  return [ordered]@{ files = @($Found); directories = $Directories; capped = $Capped }
}

$Receipt = [ordered]@{
  schema = 'manzanita/v31-runner-local-exact-bootstrap-stage@1'
  generated_at = Get-UtcIso
  result = 'FAIL_RUNNER_LOCAL_EXACT_BOOTSTRAP_STAGE_NOT_COMPLETED'
  expected = [ordered]@{ filename = $ExpectedName; bytes = $ExpectedBytes; sha256 = $ExpectedSha256 }
  search = [ordered]@{ roots = @(); directories_visited = 0; caps_reached = 0; named_candidates = 0; wrong_identity_candidates = 0 }
  selected = $null
  output = [ordered]@{ written = $false; bytes = $null; sha256 = $null }
  authority = [ordered]@{
    arbitrary_file_content_read = $false
    candidate_file_content_read_for_hash_and_zip_verification_only = $true
    operator_storage_recovery_invoked = $false
    production_inputs_materialized = 0
    receiving_intake_invoked = $false
    production_admission_invoked = $false
    product_mutation = $false
    merge_authorized = $false
    release_authorized = $false
    external_effect = 'runner-local exact-package staging only'
  }
  error = $null
}
$ExitCode = 3
try {
  $Exact = [Collections.Generic.List[object]]::new()
  $Wrong = [Collections.Generic.List[object]]::new()
  $Already = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

  $Explicit = $env:V31_EXACT_BOOTSTRAP_PATH
  if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
    if (Test-Path -LiteralPath $Explicit -PathType Leaf) {
      $Already.Add([IO.Path]::GetFullPath($Explicit)) | Out-Null
      $Size = (Get-Item -LiteralPath $Explicit).Length
      $Digest = if ($Size -eq $ExpectedBytes) { Get-Sha256 $Explicit } else { $null }
      if ($Size -eq $ExpectedBytes -and $Digest -eq $ExpectedSha256) {
        $Exact.Add([pscustomobject]@{ source_class = 'explicit-environment-path'; path = $Explicit; bytes = $Size; sha256 = $Digest })
      } else {
        $Wrong.Add([pscustomobject]@{ source_class = 'explicit-environment-path'; bytes = $Size; sha256 = $Digest })
      }
    }
  }

  $Roots = [Collections.Generic.List[object]]::new()
  Add-SearchRoot $Roots 'runner-temp' $env:RUNNER_TEMP 4
  Add-SearchRoot $Roots 'user-downloads' $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'Downloads' } else { $null }) 4
  Add-SearchRoot $Roots 'user-desktop' $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'Desktop' } else { $null }) 4
  Add-SearchRoot $Roots 'user-documents' $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'Documents' } else { $null }) 4
  Add-SearchRoot $Roots 'user-onedrive' $env:OneDrive 5
  Add-SearchRoot $Roots 'user-google-drive' $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'Google Drive' } else { $null }) 6
  Add-SearchRoot $Roots 'user-my-drive' $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'My Drive' } else { $null }) 6
  Add-SearchRoot $Roots 'g-my-drive' 'G:\My Drive' 6
  Add-SearchRoot $Roots 'g-shared-drives' 'G:\Shared drives' 5
  Add-SearchRoot $Roots 'd-projects' 'D:\Projects' 5
  Add-SearchRoot $Roots 'd-scratch' 'D:\Scratch' 5
  Add-SearchRoot $Roots 's-scratch' 'S:\Scratch' 5

  $SeenRoots = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach ($Row in $Roots) {
    try { $RootKey = [IO.Path]::GetFullPath($Row.path) } catch { continue }
    if (-not $SeenRoots.Add($RootKey)) { continue }
    $Observed = Find-Candidates -Root $Row.path -MaximumDepth $Row.maximum_depth -MaximumDirectories $MaximumDirectoriesPerRoot
    $Receipt.search.roots += [ordered]@{ source_class = $Row.source_class; present = (Test-Path -LiteralPath $Row.path -PathType Container); maximum_depth = $Row.maximum_depth; directories_visited = $Observed.directories; capped = $Observed.capped; named_candidates = @($Observed.files).Count }
    $Receipt.search.directories_visited += $Observed.directories
    if ($Observed.capped) { $Receipt.search.caps_reached++ }
    foreach ($Candidate in @($Observed.files)) {
      $Full = [IO.Path]::GetFullPath($Candidate)
      if (-not $Already.Add($Full)) { continue }
      $Size = (Get-Item -LiteralPath $Candidate).Length
      $Digest = if ($Size -eq $ExpectedBytes) { Get-Sha256 $Candidate } else { $null }
      if ($Size -eq $ExpectedBytes -and $Digest -eq $ExpectedSha256) {
        $Exact.Add([pscustomobject]@{ source_class = $Row.source_class; path = $Candidate; bytes = $Size; sha256 = $Digest })
      } else {
        $Wrong.Add([pscustomobject]@{ source_class = $Row.source_class; bytes = $Size; sha256 = $Digest })
      }
    }
  }

  $Receipt.search.named_candidates = $Exact.Count + $Wrong.Count
  $Receipt.search.wrong_identity_candidates = $Wrong.Count
  if ($Exact.Count -eq 0) {
    $Receipt.result = 'HOLD_EXACT_BOOTSTRAP_NOT_PRESENT_IN_RUNNER_LOCAL_OR_SYNCED_CUSTODY'
    $ExitCode = 2
  } else {
    $Selected = @($Exact | Sort-Object source_class)[0]
    $Archive = Test-ExactArchive -Path $Selected.path
    $Parent = Split-Path -Parent $OutputPath
    if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
    $Temporary = $OutputPath + '.tmp-' + [Guid]::NewGuid().ToString('N')
    Copy-Item -LiteralPath $Selected.path -Destination $Temporary -Force
    if ((Get-Item -LiteralPath $Temporary).Length -ne $ExpectedBytes -or (Get-Sha256 $Temporary) -ne $ExpectedSha256) { throw 'staged copy identity mismatch' }
    Move-Item -LiteralPath $Temporary -Destination $OutputPath -Force
    $Receipt.selected = [ordered]@{ source_class = $Selected.source_class; bytes = $Selected.bytes; sha256 = $Selected.sha256; archive = $Archive }
    $Receipt.output = [ordered]@{ written = $true; bytes = (Get-Item -LiteralPath $OutputPath).Length; sha256 = Get-Sha256 $OutputPath }
    $Receipt.result = 'PASS_EXACT_BOOTSTRAP_STAGED_FROM_RUNNER_LOCAL_OR_SYNCED_CUSTODY'
    $ExitCode = 0
  }
} catch {
  $Receipt.error = $_.Exception.Message
  $Receipt.result = 'FAIL_RUNNER_LOCAL_EXACT_BOOTSTRAP_STAGE_ABORTED'
  $ExitCode = 3
} finally {
  $Receipt.generated_at = Get-UtcIso
  Write-Receipt $Receipt
}
Write-Host "Result: $($Receipt.result)"
Write-Host "Receipt: $ReceiptPath"
exit $ExitCode
