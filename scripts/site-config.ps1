$ErrorActionPreference = 'Stop'

function Get-WpdpDataRoot {
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable.' }
    return Join-Path $env:LOCALAPPDATA 'WPDraftPublisher'
}

function ConvertTo-WpdpSiteKey([string]$Value) {
    $key = $Value.Trim().ToLowerInvariant() -replace '[^a-z0-9가-힣._-]+', '-'
    $key = $key.Trim('-', '.', '_')
    if ([string]::IsNullOrWhiteSpace($key) -or $key.Length -gt 64 -or $key -in @('.', '..')) {
        throw 'The site profile name must contain 1-64 letters, numbers, dots, underscores, or hyphens.'
    }
    return $key
}

function Read-WpdpRegistry {
    $root = Get-WpdpDataRoot
    $path = Join-Path $root 'sites.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json }
    catch { throw 'The site registry is damaged. Restore or remove sites.json before continuing.' }
}

function Write-WpdpJsonAtomic([object]$Value, [string]$Path, [int]$Depth = 8) {
    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $temporary = Join-Path $directory ('.wpdp-{0}.tmp' -f [Guid]::NewGuid().ToString('N'))
    try {
        $Value | ConvertTo-Json -Depth $Depth | Set-Content -LiteralPath $temporary -Encoding UTF8
        $null = Get-Content -LiteralPath $temporary -Raw | ConvertFrom-Json
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Assert-WpdpConfigDirectory([string]$Path) {
    $root = [IO.Path]::GetFullPath((Get-WpdpDataRoot)).TrimEnd('\')
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($resolved -ne $root -and -not $resolved.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The selected site configuration path escaped the WP Draft Publisher data directory.'
    }
    return $resolved
}

function Resolve-WpdpSite([string]$Site, [switch]$AllowMissing) {
    $root = Get-WpdpDataRoot
    $registry = Read-WpdpRegistry
    if (-not $registry) {
        $legacyCredentials = Join-Path $root 'credentials.json'
        if ((Test-Path -LiteralPath $legacyCredentials) -or $AllowMissing) {
            return [pscustomobject]@{ key = 'default'; label = 'Default site'; directory = $root; legacy = $true; site_url = $null }
        }
        throw 'No WordPress site is configured. Run setup-credentials.ps1 first.'
    }
    $selected = if ($Site) { $Site.Trim() } elseif ($env:WPDP_SITE) { $env:WPDP_SITE.Trim() } else { [string]$registry.default_site }
    $entry = @($registry.sites) | Where-Object { $_.key -eq $selected -or $_.label -eq $selected -or $_.site_url -eq $selected } | Select-Object -First 1
    if (-not $entry) {
        $available = (@($registry.sites) | ForEach-Object { $_.key }) -join ', '
        throw "Unknown site profile '$selected'. Available profiles: $available"
    }
    $directory = Assert-WpdpConfigDirectory (Join-Path $root ([string]$entry.directory))
    return [pscustomobject]@{ key = [string]$entry.key; label = [string]$entry.label; directory = $directory; legacy = ([string]$entry.directory -eq '.'); site_url = [string]$entry.site_url }
}

function Register-WpdpSite([string]$Key, [string]$Label, [string]$SiteUrl, [switch]$SetDefault) {
    $root = Get-WpdpDataRoot
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    $registry = Read-WpdpRegistry
    if (-not $registry) {
        $sites = @()
        $legacyPath = Join-Path $root 'credentials.json'
        if (Test-Path -LiteralPath $legacyPath) {
            $legacy = Get-Content -LiteralPath $legacyPath -Raw | ConvertFrom-Json
            $legacyHost = ([Uri][string]$legacy.site_url).Host
            $legacyKey = ConvertTo-WpdpSiteKey $legacyHost
            $sites += [ordered]@{ key = $legacyKey; label = $legacyHost; site_url = [string]$legacy.site_url; directory = '.' }
        }
        $registry = [pscustomobject]@{ schema_version = 1; default_site = if ($sites.Count) { $sites[0].key } else { $Key }; sites = $sites }
    }
    $items = @($registry.sites)
    $collision = $items | Where-Object { $_.key -eq $Key -and $_.site_url -ne $SiteUrl } | Select-Object -First 1
    if ($collision) { throw "Site profile '$Key' already belongs to another URL." }
    $urlCollision = $items | Where-Object { $_.site_url -eq $SiteUrl -and $_.key -ne $Key } | Select-Object -First 1
    if ($urlCollision) { throw "This WordPress URL is already registered as '$($urlCollision.key)'. Reconfigure that profile or remove it first." }
    $replacement = [ordered]@{ key = $Key; label = $Label; site_url = $SiteUrl; directory = "sites/$Key" }
    $updated = @($items | Where-Object { $_.key -ne $Key }) + @($replacement)
    if ($SetDefault -or -not $registry.default_site) { $registry.default_site = $Key }
    $registry.sites = $updated
    Write-WpdpJsonAtomic $registry (Join-Path $root 'sites.json')
    return Assert-WpdpConfigDirectory (Join-Path $root "sites/$Key")
}
