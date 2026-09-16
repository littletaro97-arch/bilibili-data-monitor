param(
    [string]$AndroidRoot = "",
    [string]$WindowsRoot = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($AndroidRoot)) {
    $AndroidRoot = (Get-ChildItem -LiteralPath $PSScriptRoot -Directory | Where-Object Name -like "*-android" | Select-Object -First 1).FullName
}
if ([string]::IsNullOrWhiteSpace($WindowsRoot)) {
    $WindowsRoot = (Get-ChildItem -LiteralPath $PSScriptRoot -Directory | Where-Object Name -like "*-windows" | Select-Object -First 1).FullName
}
if ([string]::IsNullOrWhiteSpace($AndroidRoot) -or [string]::IsNullOrWhiteSpace($WindowsRoot)) {
    throw "Could not locate both platform workspace directories beneath the script directory."
}
$androidContract = Join-Path $AndroidRoot "shared\history-exchange"
$windowsContract = Join-Path $WindowsRoot "shared\history-exchange"

foreach ($path in @($androidContract, $windowsContract)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Shared contract directory is missing: $path"
    }
}

function Get-ContractHashes([string]$root) {
    $result = @{}
    Get-ChildItem -LiteralPath $root -File -Recurse | ForEach-Object {
        $relative = $_.FullName.Substring($root.Length + 1).Replace('\', '/')
        $result[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
    return $result
}

$android = Get-ContractHashes $androidContract
$windows = Get-ContractHashes $windowsContract
$paths = @($android.Keys + $windows.Keys | Sort-Object -Unique)
$differences = @()
foreach ($path in $paths) {
    if ($android[$path] -ne $windows[$path]) {
        $differences += $path
    }
}

if ($differences.Count -gt 0) {
    Write-Error "Shared contract differs between platforms:`n$($differences -join [Environment]::NewLine)"
    exit 1
}

Write-Host "Shared contract is identical across $($paths.Count) files."
