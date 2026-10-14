$ErrorActionPreference = 'Stop'

$siteUrl = Read-Host 'WordPress site URL (for example, https://example.com)'
if ([string]::IsNullOrWhiteSpace($siteUrl)) { throw 'A site URL is required.' }
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
    site_url = $siteUrl.TrimEnd('/')
    username = $username
    encrypted_password = $encryptedPassword
} | ConvertTo-Json | Set-Content -LiteralPath $credentialPath -Encoding UTF8

Write-Host "Credentials saved: $credentialPath"
Write-Host 'The application password can only be decrypted by the current Windows user.'
