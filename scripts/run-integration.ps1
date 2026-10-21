param(
    [string]$WordPressImage = 'wordpress:latest',
    [ValidateSet('all', 'core', 'rank-math', 'yoast', 'aioseo', 'no-seo', 'multi-seo')]
    [string]$Scenario = 'all',
    [switch]$KeepEnvironment
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$integration = (Resolve-Path (Join-Path $root 'integration')).Path
$compose = Join-Path $integration 'docker-compose.yml'
$runtime = Join-Path $integration '.runtime'
$certs = Join-Path $runtime 'certs'
$integrationPrefix = $integration.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

if (-not $runtime.StartsWith($integrationPrefix, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($runtime) -ne '.runtime') {
    throw 'Integration runtime path escaped the project directory.'
}

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is installed but its engine is not running.' }

$env:WPDP_WORDPRESS_IMAGE = $WordPressImage
$env:WPDP_CLI_IMAGE = if ($WordPressImage -match 'php7\.4') { 'wordpress:cli-php7.4' } else { 'wordpress:cli-2.12-php8.3' }

function Invoke-Compose([string[]]$Arguments) {
    & docker compose -f $compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed: $($Arguments -join ' ')" }
}

function Invoke-Wp([string[]]$Arguments) {
    $output = & docker compose -f $compose run --rm --no-deps cli wp @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WP-CLI failed: $($Arguments -join ' ')" }
    return ($output | Out-String).Trim()
}

try {
    Invoke-Compose @('down', '-v', '--remove-orphans')
    if (Test-Path -LiteralPath $runtime) {
        $resolvedRuntime = (Resolve-Path -LiteralPath $runtime).Path
        if (-not $resolvedRuntime.StartsWith($integrationPrefix, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolvedRuntime) -ne '.runtime') {
            throw 'Refusing to clear an unexpected integration runtime path.'
        }
        Remove-Item -LiteralPath $resolvedRuntime -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $certs | Out-Null

    Invoke-Compose @('--profile', 'setup', 'run', '--rm', 'certgen')
    Invoke-Compose @('up', '-d', 'db', 'wordpress')

    $filesReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        & docker compose -f $compose exec -T wordpress test -f /var/www/html/wp-config.php
        if ($LASTEXITCODE -eq 0) { $filesReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $filesReady) { throw 'WordPress configuration was not initialized in time.' }

    Invoke-Wp @('core', 'install', '--url=https://localhost', '--title=WPDP Integration', '--admin_user=admin', '--admin_password=integration-admin-password', '--admin_email=admin@example.test', '--skip-email') | Out-Null
    Invoke-Wp @('rewrite', 'structure', '/%postname%/', '--hard') | Out-Null
    Invoke-Wp @('rewrite', 'flush', '--hard') | Out-Null
    Invoke-Wp @('plugin', 'activate', 'wp-draft-publisher-bridge') | Out-Null
    $editorId = Invoke-Wp @('user', 'create', 'integration-editor', 'editor@example.test', '--role=editor', '--user_pass=integration-editor-password', '--porcelain')
    $applicationPassword = Invoke-Wp @('user', 'application-password', 'create', $editorId, 'wpdp-integration', '--porcelain')

    Invoke-Compose @('up', '-d', 'proxy')
    $webReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        & curl.exe --silent --show-error --fail --insecure https://localhost/wp-json/ *> $null
        if ($LASTEXITCODE -eq 0) { $webReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $webReady) { throw 'The HTTPS WordPress endpoint was not ready in time.' }

    $env:IK_WP_SITE_URL = 'https://localhost'
    $env:IK_WP_USERNAME = 'integration-editor'
    $env:IK_WP_APP_PASSWORD = $applicationPassword
    $env:WPDP_TEST_CA_FILE = Join-Path $certs 'localhost.crt'

    if ($Scenario -in @('all', 'core')) {
        & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario core
        if ($LASTEXITCODE -ne 0) { throw 'Core WordPress integration tests failed.' }
    }
    if ($Scenario -in @('all', 'no-seo')) {
        & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario seo-provider --provider wordpress
        if ($LASTEXITCODE -ne 0) { throw 'WordPress native SEO fallback integration tests failed.' }
    }
    if ($Scenario -in @('all', 'rank-math')) {
        Invoke-Wp @('plugin', 'install', 'seo-by-rank-math', '--activate') | Out-Null
        & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario rank-math
        if ($LASTEXITCODE -ne 0) { throw 'Rank Math integration tests failed.' }
    }
    if ($Scenario -in @('all', 'yoast', 'multi-seo')) {
        Invoke-Wp @('plugin', 'install', 'wordpress-seo', '--activate') | Out-Null
        if ($Scenario -ne 'multi-seo') {
            & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario seo-provider --provider yoast
            if ($LASTEXITCODE -ne 0) { throw 'Yoast SEO integration tests failed.' }
        }
    }
    if ($Scenario -in @('all', 'aioseo', 'multi-seo')) {
        Invoke-Wp @('plugin', 'install', 'all-in-one-seo-pack', '--activate') | Out-Null
        if ($Scenario -ne 'multi-seo') {
            & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario seo-provider --provider aioseo
            if ($LASTEXITCODE -ne 0) { throw 'AIOSEO integration tests failed.' }
        }
    }
    if ($Scenario -in @('all', 'multi-seo')) {
        if ($Scenario -eq 'all') {
            # Rank Math is already installed by the all-scenarios block above.
        } else {
            Invoke-Wp @('plugin', 'install', 'seo-by-rank-math', '--activate') | Out-Null
        }
        & python (Join-Path $root 'tests\integration\test_live_wordpress.py') --scenario multiple-seo
        if ($LASTEXITCODE -ne 0) { throw 'Multiple SEO plugin integration tests failed.' }
    }
}
finally {
    Remove-Item Env:IK_WP_APP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_TEST_CA_FILE -ErrorAction SilentlyContinue
    if (-not $KeepEnvironment) {
        & docker compose -f $compose down -v --remove-orphans
        if (Test-Path -LiteralPath $runtime) {
            $resolvedRuntime = (Resolve-Path -LiteralPath $runtime).Path
            if (-not $resolvedRuntime.StartsWith($integrationPrefix, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolvedRuntime) -ne '.runtime') {
                throw 'Refusing to clear an unexpected integration runtime path.'
            }
            Remove-Item -LiteralPath $resolvedRuntime -Recurse -Force
        }
    }
    Remove-Item Env:WPDP_WORDPRESS_IMAGE -ErrorAction SilentlyContinue
    Remove-Item Env:WPDP_CLI_IMAGE -ErrorAction SilentlyContinue
}
