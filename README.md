# WP Draft Publisher Skill

A small Codex skill for creating image-rich WordPress drafts through the official REST API. It replaces repetitive browser editing with one compact, deterministic operation.

[한국어 안내](README.ko.md) · [Installation](docs/INSTALL.md) · [User scenarios](docs/USER-SCENARIOS.md) · [Security](SECURITY.md)

Current project version: **1.0.1**. The WordPress bridge is version **1.6.0** and follows its own compatibility version.

Local release readiness and the GitHub-only final gates are recorded in [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md). Maintainers can run the complete pre-release check with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1`.

## What it does

- Creates and updates drafts
- Updates an existing draft with the same slug instead of creating a duplicate or silently keeping stale content
- Reuses local images by SHA-256 content hash
- Retries transient read failures without blindly repeating writes
- Removes only media created by a failed operation when rollback is safe
- Refuses to update published, private, scheduled, pending, or trashed posts
- Validates the complete payload and every image before the first server mutation
- Uploads a featured image and inline images
- Adds alt text and captions
- Resolves or creates categories and tags
- Inserts valid Gutenberg-friendly figure markup
- Detects and saves Rank Math, Yoast SEO, or AIOSEO title, description, and focus keyword fields
- Falls back to the native WordPress title and excerpt when no supported SEO plugin is active
- Runs pre-save structure, SEO, link, source, duplicate-title, image-spacing, and mobile-markup checks
- Reads the saved draft back and verifies its core fields before reporting success
- Returns compact JSON suitable for low-token agent workflows
- Exposes the same guarded workflow to Claude, Cursor, and other stdio MCP clients
- Keeps credentials and editorial rules isolated across multiple named WordPress sites
- Builds read-only content plans from category gaps, similar titles, internal-link candidates, and optional Search Console exports

The command intentionally has no publish operation.

## Requirements

- Windows PowerShell 5.1 or later
- Python 3.9 or later, using only the standard library
- WordPress 5.6 or later with HTTPS and the REST API enabled
- A WordPress Application Password for an account allowed to create posts and upload media

## Install on Windows

Download `wp-draft-publisher-v1.0.1.zip` from GitHub Releases, verify its SHA-256 value against `SHA256SUMS.txt`, extract it, then double-click `install.cmd`. The installer:

- checks for Python 3.9 or later;
- runs the bundled safety tests;
- backs up an existing installation;
- copies the skill to the correct Codex directory;
- opens the secure WordPress credential setup; and
- creates a reusable editorial profile for the site's voice and content rules; and
- runs a read-only connection and capability check.

It does not need administrator access and never stores the application password in the repository.

For a non-interactive skill-only install, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SkipConfigure
```

### Manual installation

Copy this folder to:

```text
%USERPROFILE%\.codex\skills\wp-draft-publisher
```

Restart or open a new Codex conversation so the skill is discovered.

To remove the installed skill while keeping credentials:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1
```

Add `-RemoveCredentials` only when the encrypted connection details should also be removed.

See [`docs/UNINSTALL.md`](docs/UNINSTALL.md) for WordPress Application Password revocation and MCP client cleanup.

## Configure

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-credentials.ps1"
```

The application password is encrypted with Windows DPAPI and stored in the selected named site directory under `%LOCALAPPDATA%\WPDraftPublisher\sites\`. It is never stored in this repository. Existing single-site installations remain supported and migrate when reconfigured.

Create or change the non-secret editorial profile:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-profile.ps1"
```

The interactive profile uses site name, language, categories, and SEO details detected during connection as suggested answers. It records the blog topic, audience, tone, typical length, image direction, default category, FAQ preference, internal-link minimum, official-source policy, and SEO provider. Existing answers become defaults when the profile is edited. It is stored outside the installed skill so upgrades do not overwrite it. Agents read it with `scripts/show-profile.ps1` or the `wpdp_profile` MCP tool before drafting.

Verify the connection:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" verify
```

### Multiple WordPress sites

Add a site, configure its editorial profile, list sites, or change the default:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-credentials.ps1" -ProfileName "company"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-profile.ps1" -Site "company"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\list-sites.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\set-default-site.ps1" -Site "company"
```

Use `run.ps1 --site company <command>` for a one-off CLI selection. Set `WPDP_SITE=company` in an MCP server entry to bind that MCP session to one site. Each site keeps separate encrypted credentials, detected connection details, and editorial preferences. Remove one local profile with `remove-site.ps1 -Site company`; also revoke its Application Password in WordPress.

### Read-only content planning

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" --site company content-plan --search-console "C:\reports\search-results.csv" --weeks 4 --per-week 2
```

The command reads the complete WordPress post and category inventory. It reports coverage gaps and similar titles, then uses an optional Search Console CSV or JSON export to rank new-article and update opportunities and propose internal links. The returned schedule is proposal-only; the command never creates, schedules, updates, or publishes a post. See [`references/content-planning.md`](references/content-planning.md).

## Create a draft

Prepare a payload using `references/payload-schema.md`, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" draft --input "C:\path\draft.json"
```

## Use with Claude, Cursor, or another MCP client

The repository includes a dependency-free stdio MCP server. It exposes site/profile discovery, doctor, quality-check, preview-plan/dry-run, content planning, draft create/update, compact inspection, recovery snapshots, and activity history. There is deliberately no publish tool.

On Windows, complete the normal credential setup once and configure the MCP client to launch:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\YOUR_NAME\.codex\skills\wp-draft-publisher\scripts\run-mcp.ps1
```

An editable Claude Desktop example is available at [`examples/claude-desktop-config.json`](examples/claude-desktop-config.json). Cursor and other stdio MCP clients use the same command and arguments. Restart the client after saving its MCP configuration.

On macOS or Linux, run `scripts/mcp_server.py` with Python 3.9 or later and provide `IK_WP_SITE_URL`, `IK_WP_USERNAME`, and `IK_WP_APP_PASSWORD` through the operating system's secret-aware launcher. Do not save an application password in the repository or a shared configuration file.

The MCP server writes only JSON-RPC messages to stdout. WordPress failures are returned as compact tool errors without echoing credentials or full article content.

## Diagnose and inspect

Run a read-only capability check before using a new site or account:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" doctor
```

Inspect one post without returning its full body:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" inspect --id 123
```

Both commands issue authenticated `GET` requests only. `doctor` reports authentication and read access for posts, media, categories, and tags. `inspect` returns a compact status, taxonomy, featured-image, and SEO-presence summary.

## Preview without changes

Run the focused quality audit without changing WordPress:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" quality-check --input "C:\path\draft.json"
```

The report includes a score, blocking structural errors, and recommendations. `warn` mode reports recommendations without blocking a safe draft; `strict` mode blocks them. See [`references/quality-checks.md`](references/quality-checks.md).

Run the full validation and show a concise pre-save plan without creating or updating anything:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" preview-plan --input "C:\path\draft.json"
```

To preview an update, include the existing draft ID:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" preview-plan --id 123 --input "C:\path\draft.json"
```

Preview-plan (also available as `dry-run`) may issue authenticated `GET` requests to verify the target draft, existing media, categories, and tags. It summarizes the target, image uploads/reuse, taxonomy, SEO provider, quality score, and safety rules. It never sends `POST`, `PUT`, `PATCH`, or `DELETE` requests and returns `"would_mutate": false`.

`update-draft` first verifies that the target is still a draft. It stops before uploading media or changing taxonomy when the post has any other status. Update requests also omit the WordPress `status` field, so this tool cannot turn an existing public post back into a draft.

Every payload must include a stable, non-empty `slug`. A repeated `draft` command updates the existing draft with that exact slug in place. A slug owned by a published, scheduled, private, pending, or trashed post is treated as a conflict. Local images use deterministic `wpdp-<sha256>` media slugs, so byte-identical files are reused even when their local filenames differ.

Draft updates use optimistic locking. The client records the draft's `modified_gmt` value before preparing media and taxonomy, checks it again before the write, and sends it to bridge version 1.1.0 or later for an atomic server-side comparison. If a person or another process changed the draft, the update stops with `post_changed_since_read` instead of overwriting newer work.

After the post and SEO requests, the helper reads the post back in edit context and verifies the title, slug, raw body, excerpt, featured image, categories, and tags. A successful write returns `"verification_status":"verified"`. Keep the WordPress block editor closed during the command because a stale browser autosave can overwrite a REST update after it is saved.

Bridge version 1.2.0 or later stores a private server-side snapshot before each guarded draft update and retains the newest 20 snapshots per post. List recovery points with `scripts/run.ps1 snapshots --id <post-id>`. Restore one with `scripts/run.ps1 restore-snapshot --snapshot-id <snapshot-id>`. Restoration is permission checked, works only on drafts, verifies the result, and creates another recovery point before changing the post.

Bridge version 1.3.0 or later also keeps a privacy-safe activity trail for agent draft creates, updates, restores, and the media IDs involved. It records no credentials, article body, or prompt text. Bridge 1.5.0 adds **Tools → Draft Publisher**, where editors can review server readiness, setup guidance, recent activity, and permitted recovery snapshots. The same activity data is available with `scripts/run.ps1 activity --limit 50`. The newest 500 records are retained.

Authenticated `GET` requests use short, bounded retries for temporary connection failures and HTTP 429/502/503/504 responses. Mutating requests are sent once. If a create response is uncertain, the helper checks the stable slug before deciding whether the draft exists. When preparation or saving definitely fails, it deletes only attachments created during that operation; reused media is never rolled back.

## Tests

The test suite uses a mocked REST boundary and never writes to a WordPress site. It also asserts that dry-run performs read-only requests:

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.9 and 3.13 on Windows and Ubuntu.

## Releases

Release tags use `vMAJOR.MINOR.PATCH` and must match the `VERSION` file. A tag triggers unit tests, the real WordPress integration matrix, the public-file security scan, deterministic artifact builds, checksum verification, and GitHub Release creation.

Each release contains:

- `wp-draft-publisher-vX.Y.Z.zip` — complete installer package;
- `draft-publisher-rest-bridge.zip` — optional WordPress bridge plugin;
- `SHA256SUMS.txt` — artifact checksums; and
- `release-manifest.json` — machine-readable version and hashes.

Maintainers should complete [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) before pushing a release tag.

### Real WordPress integration tests

Docker tests start disposable MariaDB, WordPress, WP-CLI, and HTTPS reverse-proxy containers. They install WordPress, activate bridge 1.6.0, create a restricted editor and Application Password, and test the real REST boundary.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-integration.ps1
```

The suite verifies actual draft, media, category, and tag creation; server read-back; quality checks; native WordPress SEO fallback; Rank Math, Yoast, and AIOSEO metadata; explicit provider selection with all supported SEO plugins active; guarded concurrent updates; recovery snapshots; and recovery after the server commits a create while the response is lost. The environment and volumes are removed after the run. Add `-KeepEnvironment` only while debugging.

GitHub Actions runs the core suite on WordPress 5.6 with PHP 7.4 and the full SEO matrix on the current WordPress image with PHP 8.3. The local endpoint uses a temporary two-day certificate trusted only by the test process.

## Preflight validation

Before uploading media or creating taxonomy terms, the helper validates required text and SEO fields, taxonomy arrays, image policy values, image sources, alt text, marker uniqueness, exact marker placement, headings, FAQ structure, links, duplicate titles, source coverage, image spacing, and responsive markup risks. Local files must use absolute paths and contain a valid JPEG, PNG, GIF, WebP, or AVIF signature. Existing WordPress media IDs are resolved with read-only requests before any upload begins. SVG and extension-spoofed files are rejected.

## SEO providers

Payloads may select `auto`, `rank-math`, `yoast`, `aioseo`, or `none`. `auto` uses the first active supported provider reported by the bridge. `none`, or a site without a supported plugin, keeps the native WordPress title and excerpt as the search fallback.

Bridge 1.6.0 writes Rank Math and Yoast through their post-meta fields and AIOSEO through its post model, then reads the selected provider values back even when multiple SEO plugins are active. The optional, auditable bridge is included in [`wordpress-plugin/wp-draft-publisher-bridge`](wordpress-plugin/wp-draft-publisher-bridge), with a ready-to-upload ZIP at `dist/draft-publisher-rest-bridge.zip`. It also checks draft status and the REST-normalized modification time inside the same WordPress request used for an update, closing the status-change race that a client-only preflight cannot eliminate. See [`wordpress-plugin/README.md`](wordpress-plugin/README.md) for installation.

Build the ZIP from source with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-plugin.ps1
```

## Security

- Configuration and runtime validation require HTTPS on the standard port 443.
- Site URLs containing embedded credentials, query strings, fragments, whitespace, backslashes, or nonstandard ports are rejected before a network request.
- HTTP redirects are not followed, preventing the Authorization header from being replayed to a redirected destination.
- Use a dedicated WordPress user with only the permissions required for drafting and media uploads.
- Revoke its Application Password when access is no longer needed.
- Review every draft in WordPress before publishing.
- Do not commit credential files or application passwords.

## License

MIT

## Trademarks

This is an independent community project. It is not affiliated with or endorsed by the WordPress Foundation, Automattic, Rank Math, Yoast, AIOSEO, or OpenAI. WordPress and related marks belong to their respective owners; references in this repository describe compatibility only.
