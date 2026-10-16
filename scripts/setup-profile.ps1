[CmdletBinding()]
param(
    [switch]$UseDefaults,
    [string]$SiteName,
    [string]$Language,
    [string]$Audience,
    [string]$Tone,
    [string]$TargetLength,
    [string]$ImageStyle,
    [ValidateSet('when-useful', 'always', 'never')]
    [string]$FaqMode = 'when-useful',
    [ValidateRange(0, 10)]
    [int]$MinimumRelatedLinks = 2,
    [ValidateSet('required', 'preferred', 'optional')]
    [string]$OfficialSources = 'required',
    [ValidateSet('auto', 'rank-math', 'yoast', 'aioseo', 'none')]
    [string]$SeoProvider = 'auto'
)

$ErrorActionPreference = 'Stop'
$dataDirectory = Join-Path $env:LOCALAPPDATA 'WPDraftPublisher'
$credentialPath = Join-Path $dataDirectory 'credentials.json'
$profilePath = Join-Path $dataDirectory 'editorial-profile.json'

New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null

$defaultSiteName = 'My WordPress Site'
if (Test-Path -LiteralPath $credentialPath) {
    try {
        $credentials = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json
        $siteUri = [Uri][string]$credentials.site_url
        if ($siteUri.Host) { $defaultSiteName = $siteUri.Host }
    }
    catch {
        Write-Warning 'The existing credential file could not be read for a default site name.'
    }
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
        if ([int]::TryParse($value, [ref]$parsed) -and $parsed -ge $Minimum -and $parsed -le $Maximum) {
            return $parsed
        }
        Write-Host "Enter a number from $Minimum to $Maximum."
    }
}

$siteNameValue = if ($SiteName) { $SiteName.Trim() } else { $defaultSiteName }
$languageValue = if ($Language) { $Language.Trim() } else { 'en-US' }
$audienceValue = if ($Audience) { $Audience.Trim() } else { 'general readers looking for practical guidance' }
$toneValue = if ($Tone) { $Tone.Trim() } else { 'clear, practical, accurate, and approachable' }
$targetLengthValue = if ($TargetLength) { $TargetLength.Trim() } else { '1,200-2,000 words for a full guide' }
$imageStyleValue = if ($ImageStyle) { $ImageStyle.Trim() } else { 'cohesive premium editorial images without embedded text or logos' }
$faqModeValue = $FaqMode
$relatedLinksValue = $MinimumRelatedLinks
$officialSourcesValue = $OfficialSources
$seoProviderValue = $SeoProvider

if (-not $UseDefaults) {
    Write-Host 'Configure the default editorial profile. Press Enter to accept a suggested value.'
    $siteNameValue = Read-Default 'Site name' $siteNameValue
    $languageValue = Read-Default 'Article language or locale' $languageValue
    $audienceValue = Read-Default 'Primary audience' $audienceValue
    $toneValue = Read-Default 'Writing tone' $toneValue
    $targetLengthValue = Read-Default 'Typical article length' $targetLengthValue
    $imageStyleValue = Read-Default 'Preferred image style' $imageStyleValue
    $faqModeValue = Read-Choice 'FAQ policy' @('when-useful', 'always', 'never') $faqModeValue
    $relatedLinksValue = Read-BoundedInteger 'Minimum relevant internal links' $relatedLinksValue 0 10
    $officialSourcesValue = Read-Choice 'Official sources for changing or consequential facts' @('required', 'preferred', 'optional') $officialSourcesValue
    $seoProviderValue = Read-Choice 'SEO provider' @('auto', 'rank-math', 'yoast', 'aioseo', 'none') $seoProviderValue
}

$profile = [ordered]@{
    schema_version = 1
    site_name = $siteNameValue
    language = $languageValue
    audience = $audienceValue
    tone = $toneValue
    target_length = $targetLengthValue
    image_style = $imageStyleValue
    faq_mode = $faqModeValue
    minimum_related_links = $relatedLinksValue
    official_sources = $officialSourcesValue
    seo_provider = $seoProviderValue
}

$temporaryPath = Join-Path $dataDirectory ('.editorial-profile-{0}.tmp' -f [Guid]::NewGuid().ToString('N'))
try {
    $profile | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    $null = Get-Content -LiteralPath $temporaryPath -Raw | ConvertFrom-Json
    Move-Item -LiteralPath $temporaryPath -Destination $profilePath -Force
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

Write-Host "Editorial profile saved: $profilePath"
Write-Host 'It contains preferences only and does not contain the WordPress application password.'

