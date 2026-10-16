$ErrorActionPreference = 'Stop'
$profilePath = Join-Path $env:LOCALAPPDATA 'WPDraftPublisher\editorial-profile.json'

if (-not (Test-Path -LiteralPath $profilePath)) {
    [ordered]@{
        ok = $false
        configured = $false
        error = 'editorial_profile_missing'
        setup_command = 'scripts/setup-profile.ps1'
    } | ConvertTo-Json -Compress
    exit 2
}

try {
    $profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
}
catch {
    [ordered]@{
        ok = $false
        configured = $false
        error = 'editorial_profile_invalid'
    } | ConvertTo-Json -Compress
    exit 2
}

$required = @(
    'schema_version', 'site_name', 'language', 'audience', 'tone',
    'target_length', 'image_style', 'faq_mode', 'minimum_related_links',
    'official_sources', 'seo_provider'
)
foreach ($field in $required) {
    if ($null -eq $profile.$field -or ([string]$profile.$field).Trim().Length -eq 0) {
        [ordered]@{
            ok = $false
            configured = $false
            error = 'editorial_profile_missing_field'
            field = $field
        } | ConvertTo-Json -Compress
        exit 2
    }
}

[ordered]@{
    ok = $true
    configured = $true
    profile = $profile
} | ConvertTo-Json -Depth 5 -Compress

