# v1.0.0 release readiness

Last local verification: 2026-10-21

## Completed locally

- The public skill passes the skill frontmatter and scaffold validator.
- All 135 tests pass on Windows with Python 3.13 and in Linux containers with Python 3.9 and 3.13.
- The public-release scan finds no credentials, private keys, verification tokens, personal site URLs, or generated article files.
- The bridge passes PHP 8.3 syntax validation.
- WordPress 5.6/PHP 7.4 passes the real core draft, media, recovery, concurrency, and network-failure flow.
- Current WordPress/PHP 8.3 passes the same core flow plus native SEO fallback, Rank Math, Yoast SEO, AIOSEO, and explicit provider selection when all plugins are active.
- `wp-draft-publisher-v1.0.0.zip` installs under a disposable clean Windows user profile without credentials and exposes command help before configuration.
- The packaged uninstaller removes only that profile's installed skill and local configuration, leaving no tested files behind.
- The installed skill excludes tests, integration infrastructure, release sources, credentials, environment files, caches, and other runtime material.
- Both release artifacts match `SHA256SUMS.txt` and `release-manifest.json`.
- Repeated builds produce the same release ZIP SHA-256 value.
- Default article guidance now sets enforceable image minimums from visible article length and verifies image markers and rendered figures after saving.
- The final release commit has no whitespace errors under `git diff --check`.

Run the complete local gate from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1
```

Use `-SkipIntegration` only for a quick repeat after documentation or packaging-only changes. A release tag must use the full command.

## Required when the GitHub repository is created

These actions depend on the final public GitHub repository:

1. Create the public repository, add it as `origin`, and push the verified `main` branch.
2. Enable GitHub private vulnerability reporting so `SECURITY.md` points to an available channel.
3. Push the release commit and confirm the Windows/Ubuntu Python 3.9/3.13 workflow matrix passes.
4. Create the annotated tag `v1.0.0`; it must match `VERSION` exactly.
5. Wait for the release workflow, including both WordPress integration jobs and the clean Windows package job.
6. Download the public ZIPs and checksum file from the generated release, verify the checksums, and repeat the Korean installation guide once from the public URLs.

Do not publish the release when any item above fails. Fix the source, rebuild, and rerun the complete gate instead of replacing individual ZIP files by hand.
