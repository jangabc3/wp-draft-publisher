$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')

$selectedSite = Resolve-WpdpSite $env:WPDP_SITE
$credentialPath = Join-Path $selectedSite.directory 'credentials.json'
if (-not (Test-Path -LiteralPath $credentialPath)) {
    throw 'Credentials are missing. Run setup-credentials.ps1 first.'
}

$credentials = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json
[void][Reflection.Assembly]::LoadWithPartialName('System.Security')
$protectedBytes = [Convert]::FromBase64String([string]$credentials.encrypted_password)
$passwordBytes = [Security.Cryptography.ProtectedData]::Unprotect(
    $protectedBytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser
)
$plainPassword = [Text.Encoding]::UTF8.GetString($passwordBytes)

$env:IK_WP_SITE_URL = [string]$credentials.site_url
$env:IK_WP_USERNAME = [string]$credentials.username
$env:IK_WP_APP_PASSWORD = $plainPassword
$env:WPDP_ACTIVE_SITE = $selectedSite.key
$env:WPDP_PROFILE_PATH = Join-Path $selectedSite.directory 'editorial-profile.json'

try {
    & python (Join-Path $PSScriptRoot 'mcp_server.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item Env:IK_WP_APP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_ACTIVE_SITE -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_PROFILE_PATH -ErrorAction SilentlyContinue
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    $plainPassword = $null
}
