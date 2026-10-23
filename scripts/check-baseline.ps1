[CmdletBinding()]
param(
    [switch]$SkipPublicScan,
    [switch]$SkipPluginBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Get-PythonCommand {
    foreach ($candidate in @('python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw 'Python 3.9 or later is required.'
}

$python = Get-PythonCommand
Write-Host '[1/6] Parsing PowerShell entry points...'
$powerShellFiles = @(
    'install.ps1', 'uninstall.ps1',
    'scripts\site-config.ps1', 'scripts\setup-credentials.ps1',
    'scripts\setup-profile.ps1', 'scripts\show-profile.ps1',
    'scripts\list-sites.ps1', 'scripts\set-default-site.ps1',
    'scripts\remove-site.ps1', 'scripts\run.ps1', 'scripts\run-mcp.ps1'
)
foreach ($relativePath in $powerShellFiles) {
    $path = Join-Path $root $relativePath
    $tokens = $null
    $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "PowerShell parse failed: $relativePath - $($errors[0].Message)" }
}

Write-Host '[2/6] Parsing Python sources without writing bytecode...'
& $python (Join-Path $PSScriptRoot 'check_python_syntax.py')
if ($LASTEXITCODE -ne 0) { throw 'Python syntax validation failed.' }

if (-not $SkipPluginBuild) {
Write-Host '[3/6] Building the deterministic WordPress plugin ZIP...'
    & $python (Join-Path $root 'scripts\build_plugin.py')
    if ($LASTEXITCODE -ne 0) { throw 'Plugin build failed.' }
} else { Write-Host '[3/5] Plugin build skipped.' }

Write-Host '[4/6] Running unit and source-contract tests...'
& $python -m unittest discover -s (Join-Path $root 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

if (-not $SkipPublicScan) {
Write-Host '[5/6] Checking repository structure and documentation links...'
& $python (Join-Path $PSScriptRoot 'check_repository.py')
if ($LASTEXITCODE -ne 0) { throw 'Repository structure checks failed.' }

Write-Host '[6/6] Scanning public files for private or secret material...'
    & $python (Join-Path $root 'scripts\check_public_release.py')
    if ($LASTEXITCODE -ne 0) { throw 'Public release scan failed.' }
} else { Write-Host '[5/5] Public release scan skipped.' }

Write-Host '[OK] Baseline checks passed.'
