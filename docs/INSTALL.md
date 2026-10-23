# Installation guide

## Windows and Codex

1. Install Python 3.9 or later and confirm `python --version` works.
2. In WordPress, create a dedicated user with only the permissions needed to create posts and upload media.
3. Open that user's profile and create an Application Password named `WP Draft Publisher`.
4. Download `wp-draft-publisher-v1.0.2.zip` from GitHub Releases and extract it.
5. Double-click `install.cmd`.
6. Enter the HTTPS WordPress URL, username, and Application Password when prompted.
7. Wait while the wizard verifies authentication, posts, media, taxonomy, and bridge access before it stores the encrypted credential.
8. Review the detected language, categories, SEO provider, bridge version, and account permissions.
9. Complete the editorial profile prompts. Detected site name, language, categories, and SEO provider are offered as defaults; rerunning the wizard preserves existing answers.
10. Restart Codex or open a new chat.

Before each later save, the workflow runs `preview-plan` to validate the payload and summarize the target draft, media, taxonomy, SEO, quality, and safety rules without changing WordPress.

The installer runs the bundled safety tests, backs up an existing installation, installs the skill under `%USERPROFILE%\.codex\skills\wp-draft-publisher`, encrypts credentials with Windows DPAPI, and checks the WordPress connection.

## Multiple sites

Run `scripts\setup-credentials.ps1 -ProfileName "company"` for each additional WordPress site, followed by `scripts\setup-profile.ps1 -Site "company"`. List configured sites with `scripts\list-sites.ps1`, change the default with `scripts\set-default-site.ps1 -Site "company"`, or select one command with `scripts\run.ps1 --site company doctor`.

For Claude or Cursor, add `WPDP_SITE=company` to that MCP server entry. Each MCP process is bound to one site for its lifetime, preventing a mid-conversation site switch.

## Optional WordPress bridge

Install `draft-publisher-rest-bridge.zip` from the same GitHub Release through **Plugins → Add New → Upload Plugin**. The bridge adds atomic stale-update protection, recovery snapshots, activity history, and supported SEO plugin fields. Open **Tools → Draft Publisher** to review server readiness, setup guidance, recent activity, and permitted recovery points.

Activate it, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" doctor
```

Confirm the bridge, optimistic locking, snapshots, and activity checks are available.

## Claude Desktop and Cursor

Complete the Windows installation first. Use the command shown in `examples/claude-desktop-config.json` as a stdio MCP server and replace `YOUR_NAME` with the Windows account folder name. Restart the client after changing its MCP configuration.

## Troubleshooting

- `missing_credentials`: rerun `scripts/setup-credentials.ps1`.
- `Unknown site profile`: run `scripts/list-sites.ps1` and use one of the displayed keys.
- `wordpress_http_401`: recreate the Application Password and verify the username.
- `wordpress_http_403`: give the dedicated WordPress user permission to create posts and upload media.
- `wordpress_invalid_json_response`: confirm the REST API is not replaced by a hosting error page, security challenge, or redirect.
- `post_changed_since_read`: reload the draft because a person or another process changed it.
- `seo_bridge_unavailable`: install or update the bridge, or use the native WordPress fallback.

Do not paste credentials into an issue or chat transcript.
