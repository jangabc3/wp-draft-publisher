# Draft Publisher REST Bridge

This optional WordPress plugin adds narrowly scoped capabilities:

- It detects Rank Math, Yoast SEO, and AIOSEO and exposes permission-checked read/write SEO routes for drafts.
- It atomically rejects a publisher-tagged update when the target post is no longer a draft.
- It atomically rejects an update when the draft changed after the client read it.
- It keeps the newest 20 private recovery snapshots for each draft and exposes permission-checked list and restore routes.
- It keeps the newest 500 privacy-safe activity records and shows them under **Tools → Draft Publisher**.
- Its administrator screen shows server readiness, dedicated-user and Application Password guidance, recent activity, and permission-checked draft recovery controls.

## Install

1. Download `dist/draft-publisher-rest-bridge.zip` from this repository.
2. In WordPress, open **Plugins → Add New → Upload Plugin**.
3. Upload the ZIP, install it, and activate **Draft Publisher REST Bridge**.
4. Run `scripts/run.ps1 doctor` and confirm that `checks.bridge.ok`, `atomic_draft_guard`, `optimistic_locking`, `snapshots`, and `activity_log` are `true`. Review `active_seo_provider` and `seo_providers`.

The status route requires an authenticated account with `edit_posts`. Metadata writes, snapshot listing, and restoration require `edit_post` for the target post. Snapshots are private, capped at 20 per post, and deleted when the target post is permanently deleted. The administrator screen is available under **Tools → Draft Publisher**. The plugin stores no credentials and adds no publish endpoint.

SEO plugins are optional. When none is active, the client uses the WordPress title and excerpt fallback. The bridge does not install or configure an SEO plugin.
