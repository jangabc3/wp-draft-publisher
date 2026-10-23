[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Destination = (Join-Path $HOME '.codex\skills\wp-draft-publisher'),
    [switch]$SkipConfigure,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$resolvedSource = [IO.Path]::GetFullPath($source)
$resolvedDestination = [IO.Path]::GetFullPath($Destination)
$versionPath = Join-Path $source 'VERSION'
$projectVersion = if (Test-Path -LiteralPath $versionPath) { (Get-Content -LiteralPath $versionPath -Raw).Trim() } else { 'development' }

if ($resolvedSource.TrimEnd('\') -eq $resolvedDestination.TrimEnd('\')) {
    throw 'The install destination cannot be the source repository.'
}

function Get-PythonCommand {
    foreach ($candidate in @('python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw 'Python 3.9 or later is required. Install Python, then run install.cmd again.'
}

function Assert-PythonVersion([string]$PythonCommand) {
    $versionText = & $PythonCommand -c 'import sys; print(*sys.version_info[:3], sep=chr(46))'
    if ($LASTEXITCODE -ne 0 -or -not $versionText) {
        throw 'Python was found but could not be started.'
    }
    $version = [Version]$versionText.Trim()
    if ($version -lt [Version]'3.9') {
        throw "Python 3.9 or later is required. Found $version."
    }
    Write-Host "[OK] Python $version"
}

function Copy-SkillFiles([string]$From, [string]$To) {
    New-Item -ItemType Directory -Force -Path $To | Out-Null
    $excluded = @('.git', '.github', '__pycache__', 'integration', 'release', 'tests')
    foreach ($item in Get-ChildItem -LiteralPath $From -Force) {
        if ($excluded -contains $item.Name) { continue }
        Copy-Item -LiteralPath $item.FullName -Destination $To -Recurse -Force
    }
    Get-ChildItem -LiteralPath $To -Recurse -Directory -Filter '__pycache__' |
        Remove-Item -Recurse -Force
}

function Move-DirectoryPortable {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination
    )

    try {
        Move-Item -LiteralPath $Source -Destination $Destination -ErrorAction Stop
        return
    }
    catch [System.IO.IOException] {
        # A Windows directory rename can fail when a path traverses a junction
        # whose target is on another volume. A guarded copy keeps redirected
        # user profiles and D:-backed workspaces installable.
        if (Test-Path -LiteralPath $Destination) {
            Remove-Item -LiteralPath $Destination -Recurse -Force
        }
        try {
            New-Item -ItemType Directory -Force -Path $Destination | Out-Null
            Get-ChildItem -LiteralPath $Source -Force |
                Copy-Item -Destination $Destination -Recurse -Force
            Remove-Item -LiteralPath $Source -Recurse -Force
        }
        catch {
            if (Test-Path -LiteralPath $Destination) {
                Remove-Item -LiteralPath $Destination -Recurse -Force
            }
            throw
        }
    }
}

$python = Get-PythonCommand
Assert-PythonVersion $python
Write-Host "[INFO] WP Draft Publisher $projectVersion"

if (-not $SkipTests) {
    Write-Host '[1/4] Running the bundled safety tests...'
    & $python -m unittest discover -s (Join-Path $source 'tests') -q
    if ($LASTEXITCODE -ne 0) { throw 'The safety tests failed. Installation was stopped.' }
    Write-Host '[OK] Safety tests passed.'
}

$parent = Split-Path -Parent $resolvedDestination
$leaf = Split-Path -Leaf $resolvedDestination
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$staging = Join-Path $parent ('.{0}.install-{1}' -f $leaf, [Guid]::NewGuid().ToString('N'))
$localDataRoot = [Environment]::GetEnvironmentVariable('LOCALAPPDATA')
if (-not $localDataRoot) {
    $localDataRoot = [Environment]::GetFolderPath('LocalApplicationData')
}
$backupRoot = Join-Path $localDataRoot 'WPDraftPublisher\install-backups'
$backup = $null

try {
    Write-Host '[2/4] Preparing the Codex skill...'
    Copy-SkillFiles $resolvedSource $staging
    foreach ($required in @('SKILL.md', 'scripts\run.ps1', 'scripts\wordpress.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $staging $required))) {
            throw "The install package is missing $required."
        }
    }

    if ($PSCmdlet.ShouldProcess($resolvedDestination, 'Install WP Draft Publisher skill')) {
        if (Test-Path -LiteralPath $resolvedDestination) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $backup = Join-Path $backupRoot ('{0}-{1}' -f $leaf, (Get-Date -Format 'yyyyMMdd-HHmmss'))
            Move-DirectoryPortable -Source $resolvedDestination -Destination $backup
        }
        Move-DirectoryPortable -Source $staging -Destination $resolvedDestination

        # Versions through 1.0.2 kept upgrade backups beside the live skill.
        # Codex discovers every SKILL.md below .codex\skills, so those folders
        # appeared as duplicate skills. Move legacy backups outside discovery.
        foreach ($legacyBackup in Get-ChildItem -LiteralPath $parent -Directory -Filter ($leaf + '.backup-*') -ErrorAction SilentlyContinue) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $legacyDestination = Join-Path $backupRoot $legacyBackup.Name
            if (Test-Path -LiteralPath $legacyDestination) {
                $legacyDestination += '-' + [Guid]::NewGuid().ToString('N')
            }
            Move-DirectoryPortable -Source $legacyBackup.FullName -Destination $legacyDestination
        }
    }
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ($backup -and (Test-Path -LiteralPath $backup)) {
        if (Test-Path -LiteralPath $resolvedDestination) {
            Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
        }
        Move-DirectoryPortable -Source $backup -Destination $resolvedDestination
    }
    throw
}

Write-Host "[OK] Installed at $resolvedDestination"
if ($backup) { Write-Host "[INFO] Previous install backed up at $backup" }

if (-not $SkipConfigure) {
    Write-Host '[3/5] Connecting WordPress...'
    & (Join-Path $resolvedDestination 'scripts\setup-credentials.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Credential setup did not complete.' }

    Write-Host '[4/5] Setting editorial preferences...'
    & (Join-Path $resolvedDestination 'scripts\setup-profile.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Editorial profile setup did not complete.' }

    Write-Host '[5/5] Checking WordPress capabilities...'
    & (Join-Path $resolvedDestination 'scripts\run.ps1') doctor
    if ($LASTEXITCODE -ne 0) { throw 'The skill was installed, but the WordPress connection check failed.' }
}
else {
    Write-Host '[3/5] Credential setup skipped.'
    Write-Host '[4/5] Editorial profile setup skipped.'
    Write-Host '[5/5] Connection check skipped.'
}

Write-Host ''
Write-Host 'Installation complete.'
Write-Host 'Restart Codex or open a new chat, then ask:'
Write-Host '  Create a WordPress draft about <topic> and give me the preview link.'
Write-Host ''
Write-Host 'Optional Rank Math bridge ZIP:'
Write-Host ('  ' + (Join-Path $resolvedDestination 'dist\draft-publisher-rest-bridge.zip'))

