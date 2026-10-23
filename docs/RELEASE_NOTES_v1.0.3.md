# WP Draft Publisher v1.0.3

This patch fixes an upgrade packaging issue discovered during the public v1.0.2 end-to-end installation test.

Earlier installers kept the previous skill directory beside the live installation as `wp-draft-publisher.backup-*`. Because Codex discovers skills below `.codex/skills`, that safe rollback copy could appear as a duplicate skill. The installer now keeps upgrade backups under the local `WPDraftPublisher/install-backups` application-data directory and migrates legacy backup folders during an upgrade.

The packaged Windows acceptance test now starts with an existing installation and a legacy backup, then verifies that the new skill is installed, both backups are preserved outside skill discovery, first-use help works, and uninstall cleanup succeeds.

Download `wp-draft-publisher-v1.0.3.zip`, verify it with `SHA256SUMS.txt`, extract it, and run `install.cmd`. Existing credentials and editorial profiles remain outside the skill directory and are preserved.
