[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$Destination = (Join-Path $HOME '.codex\skills\wp-draft-publisher'),
    [switch]$RemoveCredentials
)

$ErrorActionPreference = 'Stop'
$resolvedDestination = [IO.Path]::GetFullPath($Destination)
$skillsRoot = [IO.Path]::GetFullPath((Join-Path $HOME '.codex\skills'))

if (-not $resolvedDestination.StartsWith($skillsRoot, [StringComparison]::OrdinalIgnoreCase)) {
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
    if (Test-Path -LiteralPath $credentialDirectory) {
        if ($PSCmdlet.ShouldProcess($credentialDirectory, 'Remove encrypted WordPress credentials')) {
            Remove-Item -LiteralPath $credentialDirectory -Recurse -Force
            Write-Host "Removed credentials: $credentialDirectory"
        }
    }
}

