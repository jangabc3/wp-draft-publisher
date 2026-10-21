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

## Completed on GitHub

- The verified `main` branch is public at <https://github.com/jangabc3/wp-draft-publisher>.
- GitHub private vulnerability reporting is enabled.
- The Windows/Ubuntu Python 3.9/3.13 matrix and both live WordPress integration jobs passed in [GitHub Actions run 39560628537](https://github.com/jangabc3/wp-draft-publisher/actions/runs/39560628537).

## Remaining release actions

1. Create the annotated tag `v1.0.0`; it must match `VERSION` exactly.
2. Wait for the release workflow, including both WordPress integration jobs and the clean Windows package job.
3. Download the public ZIPs and checksum file from the generated release, verify the checksums, and repeat the Korean installation guide once from the public URLs.

Do not publish the release when any item above fails. Fix the source, rebuild, and rerun the complete gate instead of replacing individual ZIP files by hand.
