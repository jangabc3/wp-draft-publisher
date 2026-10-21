[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$Destination = (Join-Path $HOME '.codex\skills\wp-draft-publisher'),
    [switch]$RemoveCredentials
)

$ErrorActionPreference = 'Stop'
$resolvedDestination = [IO.Path]::GetFullPath($Destination)
$skillsRoot = [IO.Path]::GetFullPath((Join-Path $HOME '.codex\skills'))
$skillsPrefix = $skillsRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

if (-not $resolvedDestination.StartsWith($skillsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to remove a directory outside the Codex skills folder.'
}

if (Test-Path -LiteralPath $resolvedDestination) {
    if ($PSCmdlet.ShouldProcess($resolvedDestination, 'Remove WP Draft Publisher skill')) {
        Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
        Write-Host "Removed skill: $resolvedDestination"
    }
}
else {
    Write-Host 'The skill is not installed.'
}

if ($RemoveCredentials) {
    $credentialDirectory = Join-Path $env:LOCALAPPDATA 'WPDraftPublisher'
    $resolvedCredentialDirectory = [IO.Path]::GetFullPath($credentialDirectory)
    $localDataRoot = [IO.Path]::GetFullPath($env:LOCALAPPDATA)
    $localDataPrefix = $localDataRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedCredentialDirectory.StartsWith($localDataPrefix, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolvedCredentialDirectory) -ne 'WPDraftPublisher') {
        throw 'Refusing to remove an unexpected credential directory.'
    }
    if (Test-Path -LiteralPath $credentialDirectory) {
        if ($PSCmdlet.ShouldProcess($credentialDirectory, 'Remove encrypted WordPress credentials')) {
            Remove-Item -LiteralPath $credentialDirectory -Recurse -Force
            Write-Host "Removed credentials: $credentialDirectory"
        }
    }
}

