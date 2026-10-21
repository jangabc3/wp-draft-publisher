$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')
$registry = Read-WpdpRegistry
if (-not $registry) {
    $site = Resolve-WpdpSite '' -AllowMissing
    $configured = Test-Path -LiteralPath (Join-Path $site.directory 'credentials.json')
    [ordered]@{ ok = $true; default_site = if ($configured) { 'default' } else { $null }; sites = if ($configured) { @([ordered]@{ key = 'default'; label = 'Default site'; site_url = $null; configured = $true }) } else { @() } } | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
[ordered]@{
    ok = $true
    default_site = [string]$registry.default_site
    sites = @($registry.sites | ForEach-Object {
        $directory = Assert-WpdpConfigDirectory (Join-Path (Get-WpdpDataRoot) ([string]$_.directory))
        [ordered]@{ key = [string]$_.key; label = [string]$_.label; site_url = [string]$_.site_url; configured = Test-Path -LiteralPath (Join-Path $directory 'credentials.json'); is_default = ([string]$_.key -eq [string]$registry.default_site) }
    })
} | ConvertTo-Json -Depth 6 -Compress
