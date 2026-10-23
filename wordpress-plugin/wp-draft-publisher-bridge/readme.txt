=== Draft Publisher REST Bridge ===
Contributors: wp-draft-publisher
Requires at least: 5.6
Requires PHP: 7.4
Stable tag: 1.6.1
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Permission-checked SEO metadata, guarded draft updates, private recovery snapshots, and an administrator connection screen for WP Draft Publisher.

== Description ==

This companion plugin provides permission-checked SEO reads and draft-only writes for Rank Math, Yoast SEO, and AIOSEO. It rejects tool-tagged REST updates when the target post is no longer a draft or changed after the agent read it. Before an accepted update it stores a private recovery snapshot. Permission-checked restoration works only for drafts, verifies the restored state, and preserves a recovery point for the state it replaced. Tools > Draft Publisher shows server readiness, setup guidance, recent activity, and recovery controls. The plugin stores no credentials and provides no publishing operation.

== Installation ==

1. Upload and activate the plugin.
2. Run the WP Draft Publisher doctor command.
3. Confirm that the bridge and atomic draft guard are reported as available.

== Changelog ==

= 1.6.1 =

* Normalize a snapshot's captured modification time when WordPress stores the raw GMT field as the zero date.

= 1.6.0 =

* Allow SEO read-back verification to select Rank Math, Yoast, AIOSEO, or WordPress explicitly when multiple SEO plugins are active.

= 1.5.0 =
* Add Tools > Draft Publisher with connection readiness, dedicated-user guidance, activity, and recovery tabs.
* Allow editors to restore permitted draft snapshots from the administrator screen.
* Report site language, WordPress version, site name, and home URL through the authenticated status route.

= 1.4.1 =
* Normalize draft modification timestamps to the RFC 3339 format returned by the WordPress REST API.
* Handle newly created drafts whose database GMT timestamp has not been initialized yet.

= 1.4.0 =
* Add automatic Rank Math, Yoast SEO, and AIOSEO detection.
* Add permission-checked SEO read and draft-only write routes.
* Include provider-neutral SEO values in recovery snapshots.

= 1.2.0 =
* Store private recovery snapshots before guarded draft updates.
* Record privacy-safe draft activity without credentials, prompts, or article content.
* Review permitted activity under Tools > Draft Publisher.
* Add permission-checked snapshot listing and verified draft-only restoration.

= 1.1.0 =
* Reject stale draft updates with an atomic modified-time comparison.

= 1.0.2 =
* Use a conflict-free installation directory for sites affected by an incomplete prior upload.

= 1.0.1 =
* Register SEO metadata after Rank Math so REST visibility remains enabled.

= 1.0.0 =
* Initial release.
