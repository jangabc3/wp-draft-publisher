[CmdletBinding()]
param(
    [string]$SiteUrl,
    [string]$Username,
    [Security.SecureString]$ApplicationPassword,
    [string]$ProfileName,
    [switch]$SetDefault,
    [switch]$SkipConnectionTest
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')

function Read-RequiredValue([string]$Prompt, [string]$CurrentValue) {
    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) { return $CurrentValue.Trim() }
    $value = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($value)) { throw "$Prompt is required." }
    return $value.Trim()
}

function Get-PythonCommand {
    foreach ($candidate in @('python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw 'Python 3.9 or later is required before WordPress can be connected.'
}

function Assert-SiteUrl([string]$Value) {
    $normalized = $Value.Trim().TrimEnd('/')
    $parsed = $null
    if (-not [Uri]::TryCreate($normalized, [UriKind]::Absolute, [ref]$parsed)) {
        throw 'The WordPress address is malformed. Example: https://example.com'
    }
    if ($parsed.Scheme -ne 'https') { throw 'The WordPress address must begin with https://.' }
    if ([string]::IsNullOrWhiteSpace($parsed.Host)) { throw 'The WordPress address must include a domain name.' }
    if (-not [string]::IsNullOrEmpty($parsed.UserInfo)) { throw 'Do not put a username or password in the WordPress address.' }
    if (-not [string]::IsNullOrEmpty($parsed.Query) -or -not [string]::IsNullOrEmpty($parsed.Fragment)) {
        throw 'Remove the query string or #fragment from the WordPress address.'
    }
    if (-not $parsed.IsDefaultPort -and $parsed.Port -ne 443) { throw 'Only the standard HTTPS port 443 is supported.' }
    if ($normalized.Contains('\') -or $normalized -match '\s') { throw 'The WordPress address contains invalid characters.' }
    return $normalized
}

function Get-FriendlyConnectionError([object]$Result) {
    $errors = @()
    if ($Result -and $Result.checks) {
        foreach ($property in $Result.checks.PSObject.Properties) {
            if (-not $property.Value.ok -and $property.Value.error) { $errors += [string]$property.Value.error }
        }
    }
    $joined = $errors -join ', '
    if ($joined -match '401|403') {
        return 'WordPress rejected the account. Use an Application Password, confirm the username, and make sure the account can create posts and upload media.'
    }
    if ($joined -match '404') {
        return 'The WordPress REST API could not be found. Save Settings > Permalinks once and check whether a security plugin blocks /wp-json/.'
    }
    if ($joined -match 'connection|timeout|certificate') {
        return 'The site could not be reached securely. Check the address, HTTPS certificate, firewall, and hosting security settings.'
    }
    return 'The connection check did not pass. Confirm the site address, username, Application Password, REST API, and account permissions.'
}

$SiteUrl = Read-RequiredValue 'WordPress site address (example: https://example.com)' $SiteUrl
$SiteUrl = Assert-SiteUrl $SiteUrl
$Username = Read-RequiredValue 'WordPress username' $Username
if (-not $ApplicationPassword) {
    $ApplicationPassword = Read-Host 'WordPress Application Password (input is hidden)' -AsSecureString
}

[void][Reflection.Assembly]::LoadWithPartialName('System.Security')
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ApplicationPassword)
$plainPassword = $null
$passwordBytes = $null
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainPassword)) { throw 'An Application Password is required.' }

    $connectionResult = $null
    if (-not $SkipConnectionTest) {
        Write-Host ''
        Write-Host '[CHECK] Connecting without saving the password...'
        $python = Get-PythonCommand
        $previousSite = $env:IK_WP_SITE_URL
        $previousUser = $env:IK_WP_USERNAME
        $previousPassword = $env:IK_WP_APP_PASSWORD
        try {
            $env:IK_WP_SITE_URL = $SiteUrl
            $env:IK_WP_USERNAME = $Username
            $env:IK_WP_APP_PASSWORD = $plainPassword
            $rawResult = & $python (Join-Path $PSScriptRoot 'wordpress.py') doctor
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            if ($null -eq $previousSite) { Remove-Item Env:IK_WP_SITE_URL -ErrorAction SilentlyContinue } else { $env:IK_WP_SITE_URL = $previousSite }
            if ($null -eq $previousUser) { Remove-Item Env:IK_WP_USERNAME -ErrorAction SilentlyContinue } else { $env:IK_WP_USERNAME = $previousUser }
            if ($null -eq $previousPassword) { Remove-Item Env:IK_WP_APP_PASSWORD -ErrorAction SilentlyContinue } else { $env:IK_WP_APP_PASSWORD = $previousPassword }
        }
        try { $connectionResult = ($rawResult -join "`n") | ConvertFrom-Json }
        catch { throw 'The connection checker returned an unreadable response. No credentials were saved.' }
        if ($pythonExitCode -ne 0 -or -not $connectionResult.ok) {
            throw ((Get-FriendlyConnectionError $connectionResult) + ' No credentials were saved.')
        }
    }

    $passwordBytes = [Text.Encoding]::UTF8.GetBytes($plainPassword)
    $protectedBytes = [Security.Cryptography.ProtectedData]::Protect(
        $passwordBytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $encryptedPassword = [Convert]::ToBase64String($protectedBytes)

    $siteHost = ([Uri]$SiteUrl).Host
    $profileLabel = if ([string]::IsNullOrWhiteSpace($ProfileName)) { $siteHost } else { $ProfileName.Trim() }
    $profileKey = ConvertTo-WpdpSiteKey $profileLabel
    $dataDirectory = Register-WpdpSite $profileKey $profileLabel $SiteUrl -SetDefault:$SetDefault
    $credentialPath = Join-Path $dataDirectory 'credentials.json'
    $connectionPath = Join-Path $dataDirectory 'connection.json'
    New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null

    $credentialTemporaryPath = Join-Path $dataDirectory ('.credentials-{0}.tmp' -f [Guid]::NewGuid().ToString('N'))
    try {
        [ordered]@{
            schema_version = 2
            site_url = $SiteUrl
            username = $Username
            encrypted_password = $encryptedPassword
        } | ConvertTo-Json | Set-Content -LiteralPath $credentialTemporaryPath -Encoding UTF8
        $null = Get-Content -LiteralPath $credentialTemporaryPath -Raw | ConvertFrom-Json
        Move-Item -LiteralPath $credentialTemporaryPath -Destination $credentialPath -Force
    }
    finally {
        if (Test-Path -LiteralPath $credentialTemporaryPath) { Remove-Item -LiteralPath $credentialTemporaryPath -Force }
    }

    if ($connectionResult) {
        $connectionMetadata = [ordered]@{
            schema_version = 1
            checked_at = (Get-Date).ToUniversalTime().ToString('o')
            site_url = $SiteUrl
            site = $connectionResult.site_details
            user = $connectionResult.user
            categories = @($connectionResult.categories)
            tags = @($connectionResult.tags)
            seo_providers = @($connectionResult.checks.bridge.seo_providers)
            active_seo_provider = $connectionResult.checks.bridge.active_seo_provider
            bridge_version = $connectionResult.checks.bridge.version
        }
        Write-WpdpJsonAtomic $connectionMetadata $connectionPath
    }

    Write-Host ''
    Write-Host '[OK] WordPress connected.'
    Write-Host "Profile: $profileKey ($profileLabel)"
    Write-Host "Site: $SiteUrl"
    if ($connectionResult -and $connectionResult.site_details.name) { Write-Host ("Name: " + $connectionResult.site_details.name) }
    if ($connectionResult -and $connectionResult.site_details.language) { Write-Host ("Language: " + $connectionResult.site_details.language) }
    if ($connectionResult -and $connectionResult.site_details.wordpress_version) { Write-Host ("WordPress: " + $connectionResult.site_details.wordpress_version) }
    $categoryCount = if ($connectionResult) { @($connectionResult.categories).Count } else { 0 }
    Write-Host "Categories found: $categoryCount"
    $seoName = if ($connectionResult -and $connectionResult.checks.bridge.active_seo_provider) { $connectionResult.checks.bridge.active_seo_provider } else { 'WordPress default' }
    Write-Host "SEO: $seoName"
    Write-Host "Encrypted credentials: $credentialPath"
    Write-Host "Use this profile explicitly: scripts/run.ps1 --site $profileKey <command>"
    Write-Host 'The Application Password can only be decrypted by this Windows user.'
}
finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    $plainPassword = $null
    Remove-Variable ApplicationPassword -ErrorAction SilentlyContinue
}
