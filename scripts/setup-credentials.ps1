$ErrorActionPreference = 'Stop'

$siteUrl = Read-Host 'WordPress site URL (for example, https://example.com)'
if ([string]::IsNullOrWhiteSpace($siteUrl)) { throw 'A site URL is required.' }
$siteUrl = $siteUrl.Trim().TrimEnd('/')
$parsedSite = $null
if (-not [Uri]::TryCreate($siteUrl, [UriKind]::Absolute, [ref]$parsedSite)) {
    throw 'The site URL is malformed.'
}
if ($parsedSite.Scheme -ne 'https') { throw 'The site URL must use HTTPS.' }
if ([string]::IsNullOrWhiteSpace($parsedSite.Host)) { throw 'The site URL must include a host.' }
if (-not [string]::IsNullOrEmpty($parsedSite.UserInfo)) {
    throw 'Do not embed a username or password in the site URL.'
}
if (-not [string]::IsNullOrEmpty($parsedSite.Query) -or -not [string]::IsNullOrEmpty($parsedSite.Fragment)) {
    throw 'The site URL cannot include a query string or fragment.'
}
if (-not $parsedSite.IsDefaultPort -and $parsedSite.Port -ne 443) {
    throw 'Only the standard HTTPS port 443 is allowed.'
}
if ($siteUrl.Contains('\') -or $siteUrl -match '\s') {
    throw 'The site URL contains invalid characters.'
}
$username = Read-Host 'WordPress username'
if ([string]::IsNullOrWhiteSpace($username)) { throw 'A username is required.' }
$password = Read-Host 'WordPress application password (input is hidden)' -AsSecureString

[void][Reflection.Assembly]::LoadWithPartialName('System.Security')
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $passwordBytes = [Text.Encoding]::UTF8.GetBytes($plainPassword)
    $protectedBytes = [Security.Cryptography.ProtectedData]::Protect(
        $passwordBytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $encryptedPassword = [Convert]::ToBase64String($protectedBytes)
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    $plainPassword = $null
}

$credentialDirectory = Join-Path $env:LOCALAPPDATA 'WPDraftPublisher'
$credentialPath = Join-Path $credentialDirectory 'credentials.json'
New-Item -ItemType Directory -Force -Path $credentialDirectory | Out-Null

[pscustomobject]@{
    site_url = $siteUrl
    username = $username
    encrypted_password = $encryptedPassword
} | ConvertTo-Json | Set-Content -LiteralPath $credentialPath -Encoding UTF8

Write-Host "Credentials saved: $credentialPath"
Write-Host 'The application password can only be decrypted by the current Windows user.'
