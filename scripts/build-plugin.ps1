$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pluginRoot = Join-Path $repositoryRoot 'wordpress-plugin\wp-draft-publisher-bridge'
$distRoot = Join-Path $repositoryRoot 'dist'
$archivePath = Join-Path $distRoot 'wp-draft-publisher-bridge.zip'

if (-not (Test-Path -LiteralPath $pluginRoot -PathType Container)) {
    throw "Plugin source not found: $pluginRoot"
}

New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

Compress-Archive -LiteralPath $pluginRoot -DestinationPath $archivePath -CompressionLevel Optimal
$archive = Get-Item -LiteralPath $archivePath
Write-Output (ConvertTo-Json @{ ok = $true; path = $archive.FullName; bytes = $archive.Length } -Compress)
