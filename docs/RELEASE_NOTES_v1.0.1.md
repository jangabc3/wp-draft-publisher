# WP Draft Publisher v1.0.1

This maintenance release fixes installation for Windows users whose Codex skill directory or extracted package path traverses a junction backed by another drive.

## Fixed

- The installer now falls back to a guarded recursive copy when Windows rejects a directory rename across a junction or volume boundary.
- Failed fallback copies remove partial output and restore the previous installation when an upgrade backup exists.

## Upgrade

Download `wp-draft-publisher-v1.0.1.zip`, verify it with `SHA256SUMS.txt`, extract it, and run `install.cmd`. Existing credentials and editorial profiles remain outside the skill directory and are preserved.
