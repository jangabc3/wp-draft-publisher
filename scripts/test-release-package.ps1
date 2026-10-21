[CmdletBinding()]
param(
    [string]$Package,
    [switch]$KeepTemporaryFiles
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
if (-not $Package) {
    $Package = Join-Path $root "release\wp-draft-publisher-v$version.zip"
}
$resolvedPackage = [IO.Path]::GetFullPath($Package)
if (-not (Test-Path -LiteralPath $resolvedPackage -PathType Leaf)) {
    throw "Release package was not found: $resolvedPackage"
}

$temporary = Join-Path $root ('.release-acceptance-' + [Guid]::NewGuid().ToString('N'))
$resolvedTemporary = [IO.Path]::GetFullPath($temporary)
if (-not $resolvedTemporary.StartsWith($root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The temporary acceptance directory escaped the project root.'
}

try {
    New-Item -ItemType Directory -Force -Path $resolvedTemporary | Out-Null
    Expand-Archive -LiteralPath $resolvedPackage -DestinationPath $resolvedTemporary
    $source = Join-Path $resolvedTemporary 'wp-draft-publisher'
    $fakeProfile = Join-Path $resolvedTemporary 'user-profile'
    $fakeLocalAppData = Join-Path $fakeProfile 'AppData\Local'
    $destination = Join-Path $fakeProfile '.codex\skills\wp-draft-publisher'
    if (-not (Test-Path -LiteralPath (Join-Path $source 'install.ps1'))) {
        throw 'The release ZIP does not contain wp-draft-publisher/install.ps1.'
    }

    New-Item -ItemType Directory -Force -Path $fakeLocalAppData | Out-Null
    $previousUserProfile = $env:USERPROFILE
    $previousLocalAppData = $env:LOCALAPPDATA
    $previousHome = $env:HOME
    try {
        $env:USERPROFILE = $fakeProfile
        $env:LOCALAPPDATA = $fakeLocalAppData
        $env:HOME = $fakeProfile
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $source 'install.ps1') -SkipConfigure
        if ($LASTEXITCODE -ne 0) { throw 'The extracted release installer failed.' }
    }
    finally {
        $env:USERPROFILE = $previousUserProfile
        $env:LOCALAPPDATA = $previousLocalAppData
        $env:HOME = $previousHome
    }

    foreach ($required in @('SKILL.md', 'scripts\run.ps1', 'scripts\wordpress.py', 'dist\draft-publisher-rest-bridge.zip')) {
        if (-not (Test-Path -LiteralPath (Join-Path $destination $required))) {
            throw "The installed skill is missing $required."
        }
    }
    foreach ($excluded in @('tests', 'integration', '.github', 'release')) {
        if (Test-Path -LiteralPath (Join-Path $destination $excluded)) {
            throw "Development directory leaked into the installed skill: $excluded"
        }
    }
    $privateNames = @('credentials.json', '.env', '__pycache__')
    $leaked = Get-ChildItem -LiteralPath $destination -Recurse -Force |
        Where-Object { $_.Name -in $privateNames } |
        Select-Object -First 1
    if ($leaked) { throw "Private or runtime material leaked into the installed skill: $($leaked.FullName)" }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $destination 'scripts\run.ps1') --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'The installed command could not display help before configuration.' }

    $credentialDirectory = Join-Path $fakeLocalAppData 'WPDraftPublisher'
    New-Item -ItemType Directory -Force -Path $credentialDirectory | Out-Null
    Set-Content -LiteralPath (Join-Path $credentialDirectory 'acceptance-marker.txt') -Value 'disposable'
    try {
        $env:USERPROFILE = $fakeProfile
        $env:LOCALAPPDATA = $fakeLocalAppData
        $env:HOME = $fakeProfile
        $env:WPDP_ACCEPTANCE_UNINSTALLER = Join-Path $source 'uninstall.ps1'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& $env:WPDP_ACCEPTANCE_UNINSTALLER -RemoveCredentials -Confirm:$false'
        if ($LASTEXITCODE -ne 0) { throw 'The extracted release uninstaller failed.' }
    }
    finally {
        $env:USERPROFILE = $previousUserProfile
        $env:LOCALAPPDATA = $previousLocalAppData
        $env:HOME = $previousHome
        Remove-Item Env:WPDP_ACCEPTANCE_UNINSTALLER -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $destination) { throw 'The uninstaller left the installed skill behind.' }
    if (Test-Path -LiteralPath $credentialDirectory) { throw 'The uninstaller left local configuration behind.' }

    Write-Host '[OK] Extracted release passed clean-profile install, first-use, and uninstall checks.'
}
finally {
    if (-not $KeepTemporaryFiles -and (Test-Path -LiteralPath $resolvedTemporary)) {
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}
