# v1.0.2 release readiness

Last local verification: 2026-10-24

## Reason for the maintenance release

The public v1.0.1 end-to-end test successfully created, updated, restored, and inspected a real InsightKit draft. That test also exposed a recovery-audit metadata edge case: some WordPress environments can return `0000-00-00 00:00:00` from the raw `post_modified_gmt` field even when the REST-normalized timestamp is valid.

v1.0.2 bundles bridge 1.6.1, which records the REST-normalized modification time in every recovery snapshot. The live integration contract now rejects missing or zero-date snapshot capture times.

## Completed locally

- All 135 unit and source-contract tests pass.
- PowerShell entry points and Python sources pass syntax validation.
- The public-release scan finds no credentials, private keys, verification tokens, personal site URLs, or generated article files.
- WordPress 5.6/PHP 7.4 passes the complete draft, media, taxonomy, snapshot, restore, optimistic-locking, and uncertain-response recovery flow.
- Current WordPress/PHP 8.3 passes the core flow and the WordPress, Rank Math, Yoast, AIOSEO, and simultaneous-plugin SEO matrix.
- The bridge ZIP passes deterministic packaging validation.
- `wp-draft-publisher-v1.0.2.zip` installs under a disposable Windows user profile rooted below the D:-backed workspace.
- First-use help works before credentials exist, and the packaged uninstaller removes the disposable skill and local configuration.
- Both release artifacts match `SHA256SUMS.txt` and `release-manifest.json`.
- Repeated builds produce the same release ZIP SHA-256 values.

Run the complete local gate from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1
```

Use `-SkipIntegration` only for a repeat when Docker is unavailable and the change cannot affect WordPress behavior. A public tag still requires the GitHub integration matrix to pass.

## Required GitHub and public-artifact gates

1. Push the v1.0.2 release commit and confirm the Windows/Ubuntu Python matrix and both live WordPress integration jobs pass.
2. Create and push the annotated `v1.0.2` tag.
3. Confirm the release workflow, including the clean Windows package job, passes.
4. Download the public v1.0.2 artifacts and verify them against the published checksums.
5. Repeat the Korean clean installation from the public ZIP.
6. Upgrade the real InsightKit bridge to 1.6.1, create one update snapshot, and confirm its capture time is a usable RFC 3339 value.

Do not keep the release published when any required gate fails. Fix the source, rebuild, and rerun the complete gate instead of replacing individual ZIP files by hand.
