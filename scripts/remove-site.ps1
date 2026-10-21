[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)][string]$Site,
    [switch]$KeepLocalFiles
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')

$registry = Read-WpdpRegistry
if (-not $registry) { throw 'No named site profiles exist.' }
$selected = Resolve-WpdpSite $Site
$items = @($registry.sites)
if (-not ($items | Where-Object { $_.key -eq $selected.key })) {
    throw "Unknown site profile '$Site'."
}

$target = "site profile '$($selected.key)' ($($selected.site_url))"
if (-not $PSCmdlet.ShouldProcess($target, 'Remove local WP Draft Publisher configuration')) { return }

if (-not $KeepLocalFiles) {
    if ($selected.legacy) {
        foreach ($filename in @('credentials.json', 'connection.json', 'editorial-profile.json')) {
            $legacyFile = Join-Path $selected.directory $filename
            if (Test-Path -LiteralPath $legacyFile) { Remove-Item -LiteralPath $legacyFile -Force }
        }
    }
    elseif (Test-Path -LiteralPath $selected.directory) {
        $verified = Assert-WpdpConfigDirectory $selected.directory
        $siteRoot = Assert-WpdpConfigDirectory (Join-Path (Get-WpdpDataRoot) 'sites')
        if ($verified -eq $siteRoot) { throw 'Refusing to remove the shared sites directory.' }
        Remove-Item -LiteralPath $verified -Recurse -Force
    }
}

$remaining = @($items | Where-Object { $_.key -ne $selected.key })
$registry.sites = $remaining
if ([string]$registry.default_site -eq $selected.key) {
    $registry.default_site = if ($remaining.Count) { [string]$remaining[0].key } else { $null }
}
Write-WpdpJsonAtomic $registry (Join-Path (Get-WpdpDataRoot) 'sites.json')

Write-Host "[OK] Removed local site profile: $($selected.key)"
Write-Host 'For complete revocation, delete its application password in WordPress under Users > Profile.'
