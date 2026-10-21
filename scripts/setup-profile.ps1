[CmdletBinding()]
param(
    [switch]$UseDefaults,
    [string]$Site,
    [string]$SiteName,
    [string]$SiteTopic,
    [string]$Language,
    [string]$Audience,
    [string]$Tone,
    [string]$TargetLength,
    [string]$ImageStyle,
    [string]$DefaultCategory,
    [ValidateSet('when-useful', 'always', 'never')][string]$FaqMode,
    [ValidateRange(0, 10)][Nullable[int]]$MinimumRelatedLinks,
    [ValidateSet('required', 'preferred', 'optional')][string]$OfficialSources,
    [ValidateSet('auto', 'rank-math', 'yoast', 'aioseo', 'none')][string]$SeoProvider
)

$ErrorActionPreference = 'Stop'
# site-config.ps1 keeps every profile under LOCALAPPDATA\WPDraftPublisher,
# outside the installed skill so updates cannot overwrite user preferences.
. (Join-Path $PSScriptRoot 'site-config.ps1')
$selectedSite = Resolve-WpdpSite $Site
$dataDirectory = $selectedSite.directory
$credentialPath = Join-Path $dataDirectory 'credentials.json'
$connectionPath = Join-Path $dataDirectory 'connection.json'
$profilePath = Join-Path $dataDirectory 'editorial-profile.json'
New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
    catch { Write-Warning "Could not read $Path; suggested defaults will be used."; return $null }
}
function Pick([object]$Explicit, [object]$Existing, [object]$Detected, [object]$Fallback) {
    foreach ($candidate in @($Explicit, $Existing, $Detected, $Fallback)) {
        if ($null -ne $candidate -and -not [string]::IsNullOrWhiteSpace([string]$candidate)) { return $candidate }
    }
    return $Fallback
}
function Read-Default([string]$Prompt, [string]$Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}
function Read-Choice([string]$Prompt, [string[]]$Choices, [string]$Default) {
    $display = $Choices -join '/'
    while ($true) {
        $value = Read-Host "$Prompt ($display) [$Default]"
        if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
        $normalized = $value.Trim().ToLowerInvariant()
        if ($Choices -contains $normalized) { return $normalized }
        Write-Host "Choose one of: $display"
    }
}
function Read-BoundedInteger([string]$Prompt, [int]$Default, [int]$Minimum, [int]$Maximum) {
    while ($true) {
        $value = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
        $parsed = 0
        if ([int]::TryParse($value, [ref]$parsed) -and $parsed -ge $Minimum -and $parsed -le $Maximum) { return $parsed }
        Write-Host "Enter a number from $Minimum to $Maximum."
    }
}

$connection = Read-JsonFile $connectionPath
$existing = Read-JsonFile $profilePath
$detectedSiteName = if ($connection -and $connection.site.name) { $connection.site.name } else { $null }
$detectedLanguage = if ($connection -and $connection.site.language) { $connection.site.language } else { $null }
$detectedSeo = if ($connection -and $connection.active_seo_provider) { [string]$connection.active_seo_provider } else { $null }
$detectedCategory = if ($connection -and @($connection.categories).Count -gt 0) { [string]$connection.categories[0].name } else { $null }
if (-not $detectedSiteName -and (Test-Path -LiteralPath $credentialPath)) {
    try {
        $credentials = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json
        $siteUri = [Uri][string]$credentials.site_url
        if ($siteUri.Host) { $detectedSiteName = $siteUri.Host }
    } catch {}
}

$siteNameValue = [string](Pick $SiteName $existing.site_name $detectedSiteName 'My WordPress Site')
$siteTopicValue = [string](Pick $SiteTopic $existing.site_topic $null 'practical guides and useful information')
$languageValue = [string](Pick $Language $existing.language $detectedLanguage 'en-US')
$audienceValue = [string](Pick $Audience $existing.audience $null 'general readers looking for practical guidance')
$toneValue = [string](Pick $Tone $existing.tone $null 'clear, practical, accurate, and approachable')
$targetLengthValue = [string](Pick $TargetLength $existing.target_length $null '1,200-2,000 words for a full guide')
$imageStyleValue = [string](Pick $ImageStyle $existing.image_style $null 'cohesive premium editorial images without embedded text or logos')
$defaultCategoryValue = [string](Pick $DefaultCategory $existing.default_category $detectedCategory 'Uncategorized')
$faqModeValue = [string](Pick $FaqMode $existing.faq_mode $null 'when-useful')
$relatedLinksValue = if ($null -ne $MinimumRelatedLinks) { [int]$MinimumRelatedLinks } elseif ($existing -and $null -ne $existing.minimum_related_links) { [int]$existing.minimum_related_links } else { 2 }
$officialSourcesValue = [string](Pick $OfficialSources $existing.official_sources $null 'required')
$seoProviderValue = [string](Pick $SeoProvider $existing.seo_provider $detectedSeo 'auto')
if ($seoProviderValue -notin @('auto', 'rank-math', 'yoast', 'aioseo', 'none')) { $seoProviderValue = 'auto' }

if (-not $UseDefaults) {
    Write-Host 'Configure the editorial profile. Press Enter to accept each suggested value.'
    Write-Host 'The suggestions include details detected by the WordPress connection wizard.'
    $siteNameValue = Read-Default 'Site name' $siteNameValue
    $siteTopicValue = Read-Default 'Main blog topic' $siteTopicValue
    $languageValue = Read-Default 'Article language or locale' $languageValue
    $audienceValue = Read-Default 'Primary audience' $audienceValue
    $toneValue = Read-Default 'Writing tone' $toneValue
    $targetLengthValue = Read-Default 'Typical article length' $targetLengthValue
    $imageStyleValue = Read-Default 'Preferred image style' $imageStyleValue
    $defaultCategoryValue = Read-Default 'Default category' $defaultCategoryValue
    $faqModeValue = Read-Choice 'FAQ policy' @('when-useful', 'always', 'never') $faqModeValue
    $relatedLinksValue = Read-BoundedInteger 'Minimum relevant internal links' $relatedLinksValue 0 10
    $officialSourcesValue = Read-Choice 'Official sources for changing or consequential facts' @('required', 'preferred', 'optional') $officialSourcesValue
    $seoProviderValue = Read-Choice 'SEO provider' @('auto', 'rank-math', 'yoast', 'aioseo', 'none') $seoProviderValue
}

$profile = [ordered]@{
    schema_version = 2; site_name = $siteNameValue; site_topic = $siteTopicValue
    language = $languageValue; audience = $audienceValue; tone = $toneValue
    target_length = $targetLengthValue; image_style = $imageStyleValue
    default_category = $defaultCategoryValue; faq_mode = $faqModeValue
    minimum_related_links = $relatedLinksValue; official_sources = $officialSourcesValue
    seo_provider = $seoProviderValue; updated_at = (Get-Date).ToUniversalTime().ToString('o')
}
$temporaryPath = Join-Path $dataDirectory ('.editorial-profile-{0}.tmp' -f [Guid]::NewGuid().ToString('N'))
try {
    $profile | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    $null = Get-Content -LiteralPath $temporaryPath -Raw | ConvertFrom-Json
    Move-Item -LiteralPath $temporaryPath -Destination $profilePath -Force
} finally {
    if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
}

Write-Host ''
Write-Host '[OK] Editorial profile saved.'
Write-Host "Site profile: $($selectedSite.key)"
Write-Host "Site: $siteNameValue | Topic: $siteTopicValue | Language: $languageValue"
Write-Host "Audience: $audienceValue"
Write-Host "Style: $toneValue | Length: $targetLengthValue"
Write-Host "Category: $defaultCategoryValue | FAQ: $faqModeValue | Internal links: $relatedLinksValue+"
Write-Host "Sources: $officialSourcesValue | SEO: $seoProviderValue"
Write-Host "Profile: $profilePath"
Write-Host 'It contains preferences only and does not contain the WordPress application password.'
