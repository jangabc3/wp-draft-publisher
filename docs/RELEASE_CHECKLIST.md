# Release checklist

## Code and tests

- [x] `VERSION` contains the intended semantic version.
- [x] `CHANGELOG.md` contains the release date and user-visible changes.
- [x] Unit tests pass on Python 3.9 and 3.13 on Windows and Ubuntu.
- [ ] WordPress 5.6/PHP 7.4 core integration test passes for the release commit.
- [ ] Current WordPress/PHP 8.3 full integration test passes for the release commit.
- [x] PHP lint passes for the bridge plugin.
- [x] `git diff --check` passes.

## Security and privacy

- [x] Release scan finds no credentials, private keys, personal site URLs, or generated article files.
- [x] Application Password revocation instructions are current.
- [x] `SECURITY.md` private-reporting instructions are ready; confirm the repository setting below before release.
- [x] GitHub private vulnerability reporting is enabled.

## Documentation

- [x] English and Korean installation instructions match the installer.
- [x] User scenarios reflect the available MCP tools.
- [x] Removal instructions cover local files, MCP configuration, WordPress credentials, and the bridge plugin.
- [x] Screenshots and release notes contain no private site information.

## Artifacts

- [x] Run `python scripts/build_release.py`.
- [x] Verify `wp-draft-publisher-vX.Y.Z.zip` installs and uninstalls in a disposable clean Windows user profile.
- [x] Verify `draft-publisher-rest-bridge.zip` installs and activates in disposable WordPress.
- [x] Verify every file listed in `SHA256SUMS.txt`.
- [ ] Confirm the tag is exactly `vX.Y.Z` and matches `VERSION`.

## Publish

- [ ] Push the release commit.
- [ ] Create and push the signed or annotated version tag.
- [ ] Wait for the release workflow and integration matrix to pass.
- [ ] Review the generated GitHub Release and attached files.
- [ ] Test the public download links and installation steps once more.
