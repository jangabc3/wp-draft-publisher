# WP Draft Publisher Skill

A small Codex skill for creating image-rich WordPress drafts through the official REST API. It replaces repetitive browser editing with one compact, deterministic operation.

## What it does

- Creates and updates drafts
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

`update-draft` first verifies that the target is still a draft. It stops before uploading media or changing taxonomy when the post has any other status. Update requests also omit the WordPress `status` field, so this tool cannot turn an existing public post back into a draft.

## Tests

The test suite uses a mocked REST boundary and never writes to a WordPress site:

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.9 and 3.13 on Windows and Ubuntu.

## Preflight validation

Before uploading media or creating taxonomy terms, the helper validates required text and SEO fields, taxonomy arrays, image policy values, image sources, alt text, marker uniqueness, and exact marker placement. Local files must use absolute paths and contain a valid JPEG, PNG, GIF, WebP, or AVIF signature. Existing WordPress media IDs are resolved with read-only requests before any upload begins. SVG and extension-spoofed files are rejected.

## Rank Math

Rank Math metadata is sent as WordPress post meta. Some sites do not expose these fields through REST. In that case the draft and media still save, and the command returns `rank_math_rest_unavailable` so the site owner can install a minimal permission-checked REST bridge.

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
