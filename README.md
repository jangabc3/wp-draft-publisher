# WP Draft Publisher Skill

A small Codex skill for creating image-rich WordPress drafts through the official REST API. It replaces repetitive browser editing with one compact, deterministic operation.

## What it does

- Creates and updates drafts
- Reuses an existing draft with the same slug instead of creating a duplicate
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
- Returns compact JSON suitable for low-token agent workflows

The command intentionally has no publish operation.

## Requirements

- Windows PowerShell 5.1 or later
- Python 3.9 or later, using only the standard library
- WordPress 5.6 or later with HTTPS and the REST API enabled
- A WordPress Application Password for an account allowed to create posts and upload media

## Install

Copy this folder to:

```text
%USERPROFILE%\.codex\skills\wp-draft-publisher
```

Restart or open a new Codex conversation so the skill is discovered.

## Configure

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-credentials.ps1"
```

The application password is encrypted with Windows DPAPI and stored in `%LOCALAPPDATA%\WPDraftPublisher\credentials.json`. It is never stored in this repository.

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

Every payload must include a stable, non-empty `slug`. A repeated `draft` command returns the existing draft with that exact slug without uploading media or changing content. A slug owned by a published, scheduled, private, pending, or trashed post is treated as a conflict. Local images use deterministic `wpdp-<sha256>` media slugs, so byte-identical files are reused even when their local filenames differ.

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

The optional, auditable bridge is included in [`wordpress-plugin/wp-draft-publisher-bridge`](wordpress-plugin/wp-draft-publisher-bridge). A ready-to-upload ZIP is built at `dist/wp-draft-publisher-bridge.zip`. Besides exposing the three SEO fields, the bridge checks draft status inside the same WordPress request used for an update, closing the status-change race that a client-only preflight cannot eliminate. See [`wordpress-plugin/README.md`](wordpress-plugin/README.md) for installation.

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
