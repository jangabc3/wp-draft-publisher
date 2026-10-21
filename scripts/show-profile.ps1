param([string]$Site)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')
$selectedSite = if ($env:WPDP_PROFILE_PATH) { $null } else { Resolve-WpdpSite $Site }
$profilePath = if ($env:WPDP_PROFILE_PATH) { $env:WPDP_PROFILE_PATH } else { Join-Path $selectedSite.directory 'editorial-profile.json' }
if (-not (Test-Path -LiteralPath $profilePath)) {
    [ordered]@{ ok = $false; configured = $false; error = 'editorial_profile_missing'; setup_command = 'scripts/setup-profile.ps1' } | ConvertTo-Json -Compress
    exit 2
}
try { $profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json }
catch {
    [ordered]@{ ok = $false; configured = $false; error = 'editorial_profile_invalid' } | ConvertTo-Json -Compress
    exit 2
}
$required = @('schema_version', 'site_name', 'language', 'audience', 'tone', 'target_length', 'image_style', 'faq_mode', 'minimum_related_links', 'official_sources', 'seo_provider')
foreach ($field in $required) {
    if ($null -eq $profile.$field -or ([string]$profile.$field).Trim().Length -eq 0) {
        [ordered]@{ ok = $false; configured = $false; error = 'editorial_profile_missing_field'; field = $field } | ConvertTo-Json -Compress
        exit 2
    }
}
$siteTopic = if ($profile.site_topic) { [string]$profile.site_topic } else { 'practical guides and useful information' }
$defaultCategory = if ($profile.default_category) { [string]$profile.default_category } else { 'Uncategorized' }
$normalized = [ordered]@{
    schema_version = [int]$profile.schema_version; site_name = [string]$profile.site_name
    site_topic = $siteTopic; language = [string]$profile.language; audience = [string]$profile.audience
    tone = [string]$profile.tone; target_length = [string]$profile.target_length
    image_style = [string]$profile.image_style; default_category = $defaultCategory
    faq_mode = [string]$profile.faq_mode; minimum_related_links = [int]$profile.minimum_related_links
    official_sources = [string]$profile.official_sources; seo_provider = [string]$profile.seo_provider
}
[ordered]@{
    ok = $true; configured = $true; profile = $normalized
    site_profile = if ($selectedSite) { $selectedSite.key } elseif ($env:WPDP_ACTIVE_SITE) { $env:WPDP_ACTIVE_SITE } else { 'default' }
    writing_brief = [ordered]@{
        instruction = "Write for $($normalized.audience) in $($normalized.language) with a $($normalized.tone) tone."
        scope = "Focus on $siteTopic; target $($normalized.target_length)."
        content_rules = "Use $($normalized.official_sources) official sources, $($normalized.minimum_related_links)+ relevant internal links, and FAQ mode '$($normalized.faq_mode)'."
        media = [string]$normalized.image_style; default_category = $defaultCategory; seo_provider = [string]$normalized.seo_provider
    }
} | ConvertTo-Json -Depth 6 -Compress
