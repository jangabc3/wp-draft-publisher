param([Parameter(Mandatory = $true)][string]$Site)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')
$selected = Resolve-WpdpSite $Site
$registry = Read-WpdpRegistry
if (-not $registry) { throw 'Add the site as a named profile before changing the default.' }
if (-not (Test-Path -LiteralPath (Join-Path $selected.directory 'credentials.json'))) {
    throw "Site profile '$($selected.key)' has no credentials. Run setup-credentials.ps1 for that profile first."
}
$registry.default_site = $selected.key
Write-WpdpJsonAtomic $registry (Join-Path (Get-WpdpDataRoot) 'sites.json')
Write-Host "[OK] Default WordPress site: $($selected.key) ($($selected.site_url))"
