# WP Draft Publisher Skill

A small Codex skill for creating image-rich WordPress drafts through the official REST API. It replaces repetitive browser editing with one compact, deterministic operation.

## What it does

- Creates and updates drafts
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

## Rank Math

Rank Math metadata is sent as WordPress post meta. Some sites do not expose these fields through REST. In that case the draft and media still save, and the command returns `rank_math_rest_unavailable` so the site owner can install a minimal permission-checked REST bridge.

## Security

- Use a dedicated WordPress user with only the permissions required for drafting and media uploads.
- Revoke its Application Password when access is no longer needed.
- Review every draft in WordPress before publishing.
- Do not commit credential files or application passwords.

## License

MIT

## Trademarks

This is an independent community project. It is not affiliated with or endorsed by the WordPress Foundation, Automattic, Rank Math, or OpenAI. WordPress and related marks belong to their respective owners; references in this repository describe compatibility only.
