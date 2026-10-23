# v1.0.1 release readiness

Last local verification: 2026-10-23

## Reason for the maintenance release

The public v1.0.0 ZIP and checksums downloaded successfully and matched exactly. Its clean-profile installation exposed one Windows edge case: `Move-Item` can reject a directory rename when the source or Codex skill path traverses a junction backed by another drive.

v1.0.1 adds a guarded copy fallback, removes partial fallback output on failure, and restores an upgrade backup before returning an error.

## Completed locally

- The public v1.0.0 artifacts were downloaded from GitHub and matched `SHA256SUMS.txt`.
- The junction-backed failure was reproduced from the public ZIP.
- All 135 tests pass with the installer regression contract.
- PowerShell entry points and Python sources pass syntax validation without junction-sensitive bytecode writes.
- The public-release scan finds no credentials, private keys, verification tokens, personal site URLs, or generated article files.
- The bridge passes packaging validation.
- `wp-draft-publisher-v1.0.1.zip` installs under a disposable Windows user profile rooted below the D:-backed workspace.
- First-use command help works before credentials exist.
- The packaged uninstaller removes the disposable skill and local configuration.
- Both artifacts match `SHA256SUMS.txt` and `release-manifest.json`.
- Repeated builds produce the same release ZIP SHA-256 value.

Run the complete local gate from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1
```

Use `-SkipIntegration` only for a repeat when Docker is unavailable and the change cannot affect WordPress behavior. A public tag still requires the GitHub integration matrix to pass.

## Required GitHub gates

The v1.0.1 release commit passed the Windows/Ubuntu Python matrix and both live WordPress integration jobs in [GitHub Actions run 39959361223](https://github.com/jangabc3/wp-draft-publisher/actions/runs/39959361223).

1. Create and push the annotated `v1.0.1` tag.
2. Confirm the release workflow, including the clean Windows package job, passes.
3. Download the public v1.0.1 artifacts, verify their checksums, and repeat the Korean clean installation once from the public URLs.

Do not keep the release published when any required gate fails. Fix the source, rebuild, and rerun the complete gate instead of replacing individual ZIP files by hand.
