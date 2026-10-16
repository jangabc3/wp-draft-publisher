=== Draft Publisher REST Bridge ===
Contributors: wp-draft-publisher
Requires at least: 5.6
Requires PHP: 7.4
Stable tag: 1.2.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Permission-checked SEO metadata, guarded draft updates, and private recovery snapshots for WP Draft Publisher.

== Description ==

This companion plugin exposes only the three Rank Math post-meta fields used by WP Draft Publisher. It rejects tool-tagged REST updates when the target post is no longer a draft or changed after the agent read it. Before an accepted update it stores a private recovery snapshot. Permission-checked restoration works only for drafts, verifies the restored state, and preserves a recovery point for the state it replaced. The plugin stores no credentials and provides no publishing operation.

== Installation ==

1. Upload and activate the plugin.
2. Run the WP Draft Publisher doctor command.
3. Confirm that the bridge and atomic draft guard are reported as available.

== Changelog ==

= 1.2.0 =
* Store private recovery snapshots before guarded draft updates.
* Add permission-checked snapshot listing and verified draft-only restoration.

= 1.1.0 =
* Reject stale draft updates with an atomic modified-time comparison.

= 1.0.2 =
* Use a conflict-free installation directory for sites affected by an incomplete prior upload.

= 1.0.1 =
* Register SEO metadata after Rank Math so REST visibility remains enabled.

= 1.0.0 =
* Initial release.
