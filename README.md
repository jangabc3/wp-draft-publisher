# WP Draft Publisher Skill

A small Codex skill for creating image-rich WordPress drafts through the official REST API. It replaces repetitive browser editing with one compact, deterministic operation.

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
- Attempts Rank Math title, description, and focus keyword fields
- Reads the saved draft back and verifies its core fields before reporting success
- Returns compact JSON suitable for low-token agent workflows

The command intentionally has no publish operation.

## Requirements

- Windows PowerShell 5.1 or later
- Python 3.9 or later, using only the standard library
- WordPress 5.6 or later with HTTPS and the REST API enabled
- A WordPress Application Password for an account allowed to create posts and upload media

## Install on Windows

Download and extract the release ZIP, then double-click `install.cmd`. The installer:

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

## Configure

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-credentials.ps1"
```

The application password is encrypted with Windows DPAPI and stored in `%LOCALAPPDATA%\WPDraftPublisher\credentials.json`. It is never stored in this repository.

Create or change the non-secret editorial profile:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-profile.ps1"
```

The profile records the site's language, audience, tone, typical length, image direction, FAQ preference, internal-link minimum, official-source policy, and SEO provider. It is stored outside the installed skill so upgrades do not overwrite it. Agents read it with `scripts/show-profile.ps1` before drafting.

Verify the connection:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" verify
```

## Create a draft

Prepare a payload using `references/payload-schema.md`, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" draft --input "C:\path\draft.json"
```

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

Run the full validation and inspect planned media and taxonomy actions without creating or updating anything:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" dry-run --input "C:\path\draft.json"
```

To preview an update, include the existing draft ID:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" dry-run --id 123 --input "C:\path\draft.json"
```

Dry-run may issue authenticated `GET` requests to verify the target draft, existing media, categories, and tags. It never sends `POST`, `PUT`, `PATCH`, or `DELETE` requests and returns `"would_mutate": false`.

`update-draft` first verifies that the target is still a draft. It stops before uploading media or changing taxonomy when the post has any other status. Update requests also omit the WordPress `status` field, so this tool cannot turn an existing public post back into a draft.

Every payload must include a stable, non-empty `slug`. A repeated `draft` command updates the existing draft with that exact slug in place. A slug owned by a published, scheduled, private, pending, or trashed post is treated as a conflict. Local images use deterministic `wpdp-<sha256>` media slugs, so byte-identical files are reused even when their local filenames differ.

Draft updates use optimistic locking. The client records the draft's `modified_gmt` value before preparing media and taxonomy, checks it again before the write, and sends it to bridge version 1.1.0 or later for an atomic server-side comparison. If a person or another process changed the draft, the update stops with `post_changed_since_read` instead of overwriting newer work.

After the post and SEO requests, the helper reads the post back in edit context and verifies the title, slug, raw body, excerpt, featured image, categories, and tags. A successful write returns `"verification_status":"verified"`. Keep the WordPress block editor closed during the command because a stale browser autosave can overwrite a REST update after it is saved.

Bridge version 1.2.0 or later stores a private server-side snapshot before each guarded draft update and retains the newest 20 snapshots per post. List recovery points with `scripts/run.ps1 snapshots --id <post-id>`. Restore one with `scripts/run.ps1 restore-snapshot --snapshot-id <snapshot-id>`. Restoration is permission checked, works only on drafts, verifies the result, and creates another recovery point before changing the post.

Bridge version 1.3.0 or later also keeps a privacy-safe activity trail for agent draft creates, updates, restores, and the media IDs involved. It records no credentials, article body, or prompt text. Editors can review permitted records under **Tools → Draft Publisher Activity** or run `scripts/run.ps1 activity --limit 50`. The newest 500 records are retained.

Authenticated `GET` requests use short, bounded retries for temporary connection failures and HTTP 429/502/503/504 responses. Mutating requests are sent once. If a create response is uncertain, the helper checks the stable slug before deciding whether the draft exists. When preparation or saving definitely fails, it deletes only attachments created during that operation; reused media is never rolled back.

## Tests

The test suite uses a mocked REST boundary and never writes to a WordPress site. It also asserts that dry-run performs read-only requests:

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.9 and 3.13 on Windows and Ubuntu.

## Preflight validation

Before uploading media or creating taxonomy terms, the helper validates required text and SEO fields, taxonomy arrays, image policy values, image sources, alt text, marker uniqueness, and exact marker placement. Local files must use absolute paths and contain a valid JPEG, PNG, GIF, WebP, or AVIF signature. Existing WordPress media IDs are resolved with read-only requests before any upload begins. SVG and extension-spoofed files are rejected.

## Rank Math

Rank Math metadata is sent as WordPress post meta. Some sites do not expose these fields through REST. In that case the draft and media still save, and the command returns `rank_math_rest_unavailable` so the site owner can install a minimal permission-checked REST bridge.

The optional, auditable bridge is included in [`wordpress-plugin/wp-draft-publisher-bridge`](wordpress-plugin/wp-draft-publisher-bridge). A ready-to-upload ZIP is built at `dist/draft-publisher-rest-bridge.zip`. Besides exposing the three SEO fields, the bridge checks draft status inside the same WordPress request used for an update, closing the status-change race that a client-only preflight cannot eliminate. See [`wordpress-plugin/README.md`](wordpress-plugin/README.md) for installation.

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

This is an independent community project. It is not affiliated with or endorsed by the WordPress Foundation, Automattic, Rank Math, or OpenAI. WordPress and related marks belong to their respective owners; references in this repository describe compatibility only.
