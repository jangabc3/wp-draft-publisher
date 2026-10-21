# Disposable WordPress integration environment

Run the supported entry point from the repository root:

```powershell
.\scripts\run-integration.ps1
```

Useful variants:

```powershell
.\scripts\run-integration.ps1 -WordPressImage 'wordpress:5.6-php7.4-apache' -Scenario core
.\scripts\run-integration.ps1 -WordPressImage 'wordpress:php8.3-apache' -Scenario all
.\scripts\run-integration.ps1 -KeepEnvironment
```

The script removes only this Compose project's containers, named volumes, and `integration/.runtime`. It never reads the user's saved WordPress credentials. All test credentials are fixed disposable values, the generated TLS certificate lasts two days, and the endpoint binds to local port 443.

`core` covers a site without an SEO plugin. `rank-math` assumes Rank Math is already active. `all` runs core, tests the native fallback, installs and verifies Rank Math, Yoast SEO, and AIOSEO one at a time, and finally verifies explicit provider selection when all three plugins are active.
