[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutFile,

    [string]$HostId = $env:COMPUTERNAME.ToLowerInvariant()
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Safe {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Body,
        $Fallback = $null
    )
    try { & $Body } catch { $Fallback }
}

function Get-VendorGuess {
    param([string]$Name, [string]$PnpDeviceId)
    $text = (($Name + " " + $PnpDeviceId).ToLowerInvariant())
    if ($text -match "nvidia|ven_10de") { return "NVIDIA" }
    if ($text -match "intel|ven_8086") { return "Intel" }
    if ($text -match "amd|radeon|ven_1002") { return "AMD" }
    if ($text -match "microsoft|basic display|root\\display") { return "Microsoft" }
    return "Unknown"
}

function Get-RoleCandidate {
    param([string]$Vendor, [string]$Name, [string]$PnpDeviceId)
    if ($Vendor -eq "NVIDIA") { return "dgpu" }
    if (($Vendor -eq "Intel" -or $Vendor -eq "AMD") -and $PnpDeviceId -and $PnpDeviceId -notmatch "^ROOT\\") {
        return "igpu"
    }
    return "unclassified"
}

$observedAt = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$stopwatchFrequency = [System.Diagnostics.Stopwatch]::Frequency
$clockSamples = @()
for ($i = 0; $i -lt 5; $i++) {
    $clockSamples += [ordered]@{
        wall_utc = [DateTimeOffset]::UtcNow.ToString("o")
        monotonic_ticks = [System.Diagnostics.Stopwatch]::GetTimestamp()
    }
    Start-Sleep -Milliseconds 20
}

$os = Invoke-Safe { Get-CimInstance Win32_OperatingSystem }
$computer = Invoke-Safe { Get-CimInstance Win32_ComputerSystem }
$bios = Invoke-Safe { Get-CimInstance Win32_BIOS }
$processors = @(Invoke-Safe { Get-CimInstance Win32_Processor } @())
$memoryModules = @(Invoke-Safe { Get-CimInstance Win32_PhysicalMemory } @())
$physicalDisks = @(Invoke-Safe { Get-CimInstance Win32_DiskDrive } @())
$logicalDisks = @(Invoke-Safe { Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" } @())
$videoControllers = @(Invoke-Safe { Get-CimInstance Win32_VideoController } @())

$cpuRows = @($processors | ForEach-Object {
    [ordered]@{
        name = $_.Name
        manufacturer = $_.Manufacturer
        device_id = $_.DeviceID
        processor_id = $_.ProcessorId
        cores = $_.NumberOfCores
        logical_processors = $_.NumberOfLogicalProcessors
        max_clock_mhz = $_.MaxClockSpeed
        current_clock_mhz = $_.CurrentClockSpeed
        virtualization_firmware_enabled = $_.VirtualizationFirmwareEnabled
    }
})

$memoryRows = @($memoryModules | ForEach-Object {
    [ordered]@{
        device_locator = $_.DeviceLocator
        bank_label = $_.BankLabel
        capacity_bytes = [int64]$_.Capacity
        configured_clock_mhz = $_.ConfiguredClockSpeed
        manufacturer = $_.Manufacturer
        part_number = if ($_.PartNumber) { $_.PartNumber.Trim() } else { $null }
        serial_number = $null
    }
})

$diskRows = @($physicalDisks | ForEach-Object {
    [ordered]@{
        model = $_.Model
        interface_type = $_.InterfaceType
        media_type = $_.MediaType
        size_bytes = if ($_.Size) { [int64]$_.Size } else { $null }
        pnp_device_id = $_.PNPDeviceID
        serial_number = $null
    }
})

$volumeRows = @($logicalDisks | ForEach-Object {
    [ordered]@{
        device_id = $_.DeviceID
        file_system = $_.FileSystem
        size_bytes = if ($_.Size) { [int64]$_.Size } else { $null }
        free_bytes = if ($_.FreeSpace) { [int64]$_.FreeSpace } else { $null }
        volume_name = $_.VolumeName
    }
})

$adapterRows = @($videoControllers | ForEach-Object {
    $vendor = Get-VendorGuess -Name $_.Name -PnpDeviceId $_.PNPDeviceID
    [ordered]@{
        name = $_.Name
        description = $_.Description
        pnp_device_id = $_.PNPDeviceID
        adapter_ram_bytes = if ($_.AdapterRAM) { [int64]$_.AdapterRAM } else { $null }
        driver_version = $_.DriverVersion
        driver_date = if ($_.DriverDate) { Invoke-Safe { ([Management.ManagementDateTimeConverter]::ToDateTime($_.DriverDate)).ToUniversalTime().ToString("o") } } else { $null }
        status = $_.Status
        video_processor = $_.VideoProcessor
        vendor_guess = $vendor
        role_candidate = Get-RoleCandidate -Vendor $vendor -Name $_.Name -PnpDeviceId $_.PNPDeviceID
        classification_boundary = "role_candidate is a local matching aid; operational admission still requires the estate receipt"
    }
})

$nvidiaRows = @()
$nvidiaSmiPath = Invoke-Safe { (Get-Command nvidia-smi -ErrorAction Stop).Source }
$nvidiaSmiVersion = $null
if ($nvidiaSmiPath) {
    $nvidiaSmiVersion = Invoke-Safe { (& $nvidiaSmiPath --version 2>&1 | Out-String).Trim() }
    $query = "uuid,name,memory.total,driver_version,pci.bus_id,pstate,power.limit"
    $rawRows = Invoke-Safe { & $nvidiaSmiPath "--query-gpu=$query" "--format=csv,noheader,nounits" 2>$null } @()
    foreach ($line in @($rawRows)) {
        if (-not $line) { continue }
        $parts = @($line -split "," | ForEach-Object { $_.Trim() })
        if ($parts.Count -lt 7) { continue }
        $nvidiaRows += [ordered]@{
            uuid = $parts[0]
            name = $parts[1]
            memory_total_mib = Invoke-Safe { [int64]$parts[2] }
            driver_version = $parts[3]
            pci_bus_id = $parts[4]
            pstate = $parts[5]
            power_limit_watts = Invoke-Safe { [double]$parts[6] }
        }
    }
}

$networkRows = @()
if (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue) {
    $networkRows = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
        [ordered]@{
            name = $_.Name
            interface_description = $_.InterfaceDescription
            status = [string]$_.Status
            link_speed = [string]$_.LinkSpeed
            media_type = [string]$_.MediaType
            physical_media_type = [string]$_.PhysicalMediaType
            interface_guid = [string]$_.InterfaceGuid
            mac_address = $null
            addresses_collected = $false
        }
    })
}

$runtimeRows = @()
foreach ($name in @("python", "git", "ollama", "docker", "wsl", "nvidia-smi")) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    $present = [bool]$command
    $runtimeRows += [ordered]@{
        name = $name
        present = $present
        path = if ($present) { $command.Source } else { $null }
        disabled = (-not $present)
        disabled_reason = if ($present) { $null } else { "command not found in the current process PATH" }
    }
}

$body = [ordered]@{
    schema = "axm-community-lab/windows-host-observation@1"
    observed_at = $observedAt
    host_id = $HostId
    collector = [ordered]@{
        name = "collect-windows.ps1"
        powershell = $PSVersionTable.PSVersion.ToString()
        elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        read_only = $true
    }
    system = [ordered]@{
        computer_name = $env:COMPUTERNAME
        manufacturer = if ($computer) { $computer.Manufacturer } else { $null }
        model = if ($computer) { $computer.Model } else { $null }
        os_caption = if ($os) { $os.Caption } else { $null }
        os_version = if ($os) { $os.Version } else { $null }
        os_build = if ($os) { $os.BuildNumber } else { $null }
        architecture = if ($os) { $os.OSArchitecture } else { $env:PROCESSOR_ARCHITECTURE }
        bios_manufacturer = if ($bios) { $bios.Manufacturer } else { $null }
        bios_version = if ($bios) { @($bios.BIOSVersion) } else { @() }
        machine_guid_collected = $false
    }
    cpu = $cpuRows
    memory = [ordered]@{
        total_bytes = if ($computer -and $computer.TotalPhysicalMemory) { [int64]$computer.TotalPhysicalMemory } else { $null }
        modules = $memoryRows
    }
    storage = [ordered]@{
        physical_disks = $diskRows
        logical_volumes = $volumeRows
    }
    graphics = [ordered]@{
        adapters = $adapterRows
        nvidia = $nvidiaRows
        nvidia_smi_path = $nvidiaSmiPath
        nvidia_smi_version = $nvidiaSmiVersion
    }
    network = [ordered]@{
        adapters = $networkRows
        addresses_collected = $false
    }
    runtime = $runtimeRows
    clock = [ordered]@{
        stopwatch_frequency_hz = $stopwatchFrequency
        samples = $clockSamples
        cross_host_offset_measured = $false
    }
    privacy = [ordered]@{
        serial_numbers_collected = $false
        mac_addresses_collected = $false
        ip_addresses_collected = $false
        machine_guid_collected = $false
    }
    claim_boundary = "This is a read-only host observation. Vendor and role candidates aid reconciliation but do not admit a worker, prove topology, establish cross-host clock accuracy, or measure path cost."
}

$bodyJson = $body | ConvertTo-Json -Depth 16 -Compress
$bodyBytes = [Text.Encoding]::UTF8.GetBytes($bodyJson)
$shaAlgorithm = [Security.Cryptography.SHA256]::Create()
try {
    $shaBytes = $shaAlgorithm.ComputeHash($bodyBytes)
} finally {
    $shaAlgorithm.Dispose()
}
$sha = ([BitConverter]::ToString($shaBytes) -replace "-", "").ToLowerInvariant()
$body.observation_sha256 = $sha

$destination = [IO.Path]::GetFullPath($OutFile)
$parent = [IO.Path]::GetDirectoryName($destination)
if ($parent -and -not [IO.Directory]::Exists($parent)) {
    [IO.Directory]::CreateDirectory($parent) | Out-Null
}
$json = $body | ConvertTo-Json -Depth 16
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($destination, $json + "`n", $utf8NoBom)

[ordered]@{
    ok = $true
    output = $destination
    host_id = $HostId
    observation_sha256 = $sha
    nvidia_gpu_count = $nvidiaRows.Count
    graphics_adapter_count = $adapterRows.Count
} | ConvertTo-Json -Depth 4
