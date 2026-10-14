$ErrorActionPreference = 'Stop'

$credentialPath = Join-Path $env:LOCALAPPDATA 'WordPressDraftPublisher\credentials.json'
if (-not (Test-Path -LiteralPath $credentialPath)) {
    throw 'Credentials are missing. Run setup-credentials.ps1 first.'
}

$credentials = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json
[void][Reflection.Assembly]::LoadWithPartialName('System.Security')
$protectedBytes = [Convert]::FromBase64String([string]$credentials.encrypted_password)
$passwordBytes = [Security.Cryptography.ProtectedData]::Unprotect(
    $protectedBytes,
    $null,
    [Security.Cryptography.DataProtectionScope]::CurrentUser
)
$plainPassword = [Text.Encoding]::UTF8.GetString($passwordBytes)

$env:IK_WP_SITE_URL = [string]$credentials.site_url
$env:IK_WP_USERNAME = [string]$credentials.username
$env:IK_WP_APP_PASSWORD = $plainPassword

try {
    & python (Join-Path $PSScriptRoot 'wordpress.py') @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item Env:IK_WP_APP_PASSWORD -ErrorAction SilentlyContinue
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    $plainPassword = $null
}
