[CmdletBinding()]
param(
    [switch]$SkipIntegration
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
Push-Location $root
try {
    Write-Host '[1/7] Running baseline checks...'
    & (Join-Path $PSScriptRoot 'check-baseline.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Baseline checks failed.' }

    if ($SkipIntegration) {
        Write-Host '[2/7] WordPress 5.6 integration skipped by request.'
        Write-Host '[3/7] Current WordPress integration skipped by request.'
    }
    else {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw 'Docker is required for release-candidate integration checks.'
        }
        Write-Host '[2/7] Testing WordPress 5.6 / PHP 7.4 core flow...'
        & (Join-Path $PSScriptRoot 'run-integration.ps1') -WordPressImage 'wordpress:5.6-php7.4-apache' -Scenario core
        if ($LASTEXITCODE -ne 0) { throw 'WordPress 5.6 integration failed.' }
        Write-Host '[3/7] Testing current WordPress / PHP 8.3 full SEO matrix...'
        & (Join-Path $PSScriptRoot 'run-integration.ps1') -WordPressImage 'wordpress:php8.3-apache' -Scenario all
        if ($LASTEXITCODE -ne 0) { throw 'Current WordPress integration failed.' }
    }

    Write-Host '[4/7] Building bridge and release artifacts...'
    & python (Join-Path $PSScriptRoot 'build_plugin.py')
    if ($LASTEXITCODE -ne 0) { throw 'Bridge build failed.' }
    & python (Join-Path $PSScriptRoot 'build_release.py')
    if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }

    Write-Host '[5/7] Verifying artifact checksums...'
    $checksums = Join-Path $root 'release\SHA256SUMS.txt'
    foreach ($line in Get-Content -LiteralPath $checksums) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split '  ', 2
        if ($parts.Count -ne 2) { throw "Malformed checksum line: $line" }
        $artifact = Join-Path $root ('release\' + $parts[1])
        $actual = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $parts[0].ToLowerInvariant()) { throw "Checksum mismatch: $($parts[1])" }
    }

    Write-Host '[6/7] Testing a clean install from the release ZIP...'
    & (Join-Path $PSScriptRoot 'test-release-package.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Release package acceptance failed.' }

    Write-Host '[7/7] Confirming deterministic package output...'
    $primary = Join-Path $root "release\wp-draft-publisher-v$version.zip"
    $primaryHash = (Get-FileHash -LiteralPath $primary -Algorithm SHA256).Hash
    $comparison = Join-Path $root ('.release-repeat-' + [Guid]::NewGuid().ToString('N'))
    try {
        & python (Join-Path $PSScriptRoot 'build_release.py') $comparison
        if ($LASTEXITCODE -ne 0) { throw 'Repeat release build failed.' }
        $repeat = Join-Path $comparison "wp-draft-publisher-v$version.zip"
        $repeatHash = (Get-FileHash -LiteralPath $repeat -Algorithm SHA256).Hash
        if ($primaryHash -ne $repeatHash) { throw 'Release ZIP is not deterministic.' }
    }
    finally {
        if (Test-Path -LiteralPath $comparison) { Remove-Item -LiteralPath $comparison -Recurse -Force }
    }

    Write-Host "[OK] Release candidate v$version passed all requested checks."
}
finally {
    Pop-Location
}
