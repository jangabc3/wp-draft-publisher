$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'site-config.ps1')

$commandArguments = [Collections.Generic.List[string]]::new()
foreach ($argument in $args) { $commandArguments.Add([string]$argument) }
$siteName = $null
if ($commandArguments.Count -ge 2 -and $commandArguments[0] -in @('--site', '-Site')) {
    $siteName = $commandArguments[1]
    $commandArguments.RemoveRange(0, 2)
}

# Help must remain available before first-time configuration. This also makes
# the extracted release package testable without creating credentials.
if ($commandArguments.Count -eq 0 -or $commandArguments[0] -in @('--help', '-h')) {
    & python (Join-Path $PSScriptRoot 'wordpress.py') @commandArguments
    if ($LASTEXITCODE -ne 0) { throw 'Unable to display command help.' }
    return
}

$selectedSite = Resolve-WpdpSite $siteName
$credentialPath = Join-Path $selectedSite.directory 'credentials.json'
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
    $env:WPDP_ACTIVE_SITE = $selectedSite.key
    $env:WPDP_PROFILE_PATH = Join-Path $selectedSite.directory 'editorial-profile.json'
    & python (Join-Path $PSScriptRoot 'wordpress.py') @commandArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item Env:IK_WP_APP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_ACTIVE_SITE -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_PROFILE_PATH -ErrorAction SilentlyContinue
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    $plainPassword = $null
}
