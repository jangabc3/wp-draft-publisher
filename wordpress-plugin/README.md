# Draft Publisher REST Bridge

This optional WordPress plugin adds two narrowly scoped capabilities:

- It exposes the three Rank Math post-meta fields used by WP Draft Publisher with per-post edit authorization.
- It atomically rejects a publisher-tagged update when the target post is no longer a draft.

## Install

1. Download `dist/draft-publisher-rest-bridge.zip` from this repository.
2. In WordPress, open **Plugins → Add New → Upload Plugin**.
3. Upload the ZIP, install it, and activate **Draft Publisher REST Bridge**.
4. Run `scripts/run.ps1 doctor` and confirm that `checks.bridge.ok` and `atomic_draft_guard` are `true`.

The status route requires an authenticated account with `edit_posts`. Metadata writes still require `edit_post` for the target post. The plugin stores no credentials, adds no publish endpoint, and changes no post unless a normal authenticated WordPress REST request is made.

Rank Math itself is optional. The bridge only registers compatible metadata fields; it does not install or configure Rank Math.
