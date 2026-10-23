# WP Draft Publisher v1.0.2

This patch fixes recovery snapshot metadata discovered during the public v1.0.1 end-to-end user test.

WordPress can expose a draft's raw `post_modified_gmt` value as `0000-00-00 00:00:00` in some environments even though the REST-normalized timestamp is valid. Bridge 1.6.1 now records the normalized REST modification time in every recovery snapshot, so the administrator screen and API show a useful capture timestamp.

The live WordPress integration suite now fails if a newly created update snapshot has an empty or zero-date capture timestamp.

## Install

Download `wp-draft-publisher-v1.0.2.zip`, verify it with `SHA256SUMS.txt`, extract it, and run `install.cmd`. Upload `draft-publisher-rest-bridge.zip` in WordPress and replace the existing bridge when prompted.

Existing site credentials and editorial profiles remain outside the skill directory and are preserved during an upgrade.
