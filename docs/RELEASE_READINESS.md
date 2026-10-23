# v1.0.3 release readiness

Last local verification: 2026-10-24

## Reason for the maintenance release

The public v1.0.2 ZIP passed checksum verification, clean installation, InsightKit connection, and bridge 1.6.1 production validation. Its real upgrade path exposed one installer issue: a rollback directory kept beside the live skill was itself discoverable as a duplicate Codex skill.

v1.0.3 stores upgrade backups under local application data and migrates legacy `wp-draft-publisher.backup-*` directories out of `.codex/skills`. Credentials and editorial profiles remain separate and unchanged.

## Completed locally

- All unit and source-contract tests pass.
- PowerShell entry points and Python sources pass syntax validation.
- The public-release scan finds no credentials, private keys, verification tokens, personal site URLs, or generated article files.
- WordPress 5.6/PHP 7.4 passes the complete draft, media, taxonomy, snapshot, restore, optimistic-locking, and uncertain-response recovery flow.
- Current WordPress/PHP 8.3 passes the core flow and the WordPress, Rank Math, Yoast, AIOSEO, and simultaneous-plugin SEO matrix.
- The packaged Windows acceptance test starts from an existing installation, preserves its rollback copy outside skill discovery, migrates a legacy discoverable backup, and completes first-use and uninstall checks.
- Both release artifacts match `SHA256SUMS.txt` and `release-manifest.json`.
- Repeated builds produce the same release ZIP SHA-256 values.

Run the complete local gate from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1
```

## Required GitHub and public-artifact gates

1. Push the v1.0.3 release commit and confirm the Windows/Ubuntu Python matrix and both live WordPress integration jobs pass.
2. Create and push the annotated `v1.0.3` tag.
3. Confirm the release workflow, including the clean Windows package job, passes.
4. Download the public v1.0.3 artifacts and verify them against the published checksums.
5. Upgrade the actual Codex installation from the public ZIP and confirm no backup skill remains below `.codex/skills`.
6. Confirm the existing InsightKit connection and bridge 1.6.1 remain healthy after the skill-only upgrade.

Do not keep the release published when any required gate fails. Fix the source, rebuild, and rerun the complete gate instead of replacing individual ZIP files by hand.
