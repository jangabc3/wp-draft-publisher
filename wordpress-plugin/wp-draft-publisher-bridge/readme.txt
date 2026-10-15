=== Draft Publisher REST Bridge ===
Contributors: wp-draft-publisher
Requires at least: 5.6
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Permission-checked Rank Math metadata and an atomic draft-only REST update guard for WP Draft Publisher.

== Description ==

This small companion plugin exposes only the three Rank Math post-meta fields used by WP Draft Publisher. It also rejects tool-tagged REST updates when the target post is no longer a draft. The plugin stores no credentials and provides no publishing operation.

== Installation ==

1. Upload and activate the plugin.
2. Run the WP Draft Publisher doctor command.
3. Confirm that the bridge and atomic draft guard are reported as available.

== Changelog ==

= 1.0.0 =
* Initial release.
