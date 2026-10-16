# Draft Publisher REST Bridge

This optional WordPress plugin adds four narrowly scoped capabilities:

- It exposes the three Rank Math post-meta fields used by WP Draft Publisher with per-post edit authorization.
- It atomically rejects a publisher-tagged update when the target post is no longer a draft.
- It atomically rejects an update when the draft changed after the client read it.
- It keeps the newest 20 private recovery snapshots for each draft and exposes permission-checked list and restore routes.
- It keeps the newest 500 privacy-safe activity records and shows them under **Tools → Draft Publisher Activity**.

## Install

1. Download `dist/draft-publisher-rest-bridge.zip` from this repository.
2. In WordPress, open **Plugins → Add New → Upload Plugin**.
3. Upload the ZIP, install it, and activate **Draft Publisher REST Bridge**.
4. Run `scripts/run.ps1 doctor` and confirm that `checks.bridge.ok`, `atomic_draft_guard`, `optimistic_locking`, `snapshots`, and `activity_log` are `true`.

The status route requires an authenticated account with `edit_posts`. Metadata writes, snapshot listing, and restoration require `edit_post` for the target post. Snapshots are private, capped at 20 per post, and deleted when the target post is permanently deleted. The plugin stores no credentials and adds no publish endpoint.

Rank Math itself is optional. The bridge only registers compatible metadata fields; it does not install or configure Rank Math.
