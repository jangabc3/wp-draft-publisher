---
name: wp-draft-publisher
description: Write, revise, and save WordPress articles through the official REST API with draft-first publishing, structured HTML, media uploads, taxonomy assignment, and optional Rank Math metadata. Use for self-hosted WordPress article workflows.
---

# WP Draft Publisher

Use `scripts/run.ps1` for deterministic WordPress operations instead of browser automation when the REST API can complete the task.

## Workflow

1. Follow the site's editorial requirements and [references/article-format.md](references/article-format.md).
2. Prepare at least five distinct, useful images by default: one featured image and at least four inline images.
3. Create a JSON payload using [references/payload-schema.md](references/payload-schema.md).
4. Run `scripts/run.ps1 draft --input <absolute-json-path>`.
5. Return the draft ID, preview URL, media count, and SEO status.

The helper forces `status=draft`. It resolves or creates categories and tags, uploads media with alt text and captions, inserts valid figure markup at markers, sets the featured image, and attempts Rank Math metadata.

## Existing drafts

Use `scripts/run.ps1 update-draft --id <post-id> --input <absolute-json-path>`. Reuse `media_id` values to avoid duplicate uploads.

## Credentials

Run `scripts/setup-credentials.ps1` in an interactive Windows terminal. Credentials are encrypted with Windows DPAPI and stored outside the repository. Never request, print, commit, or paste application passwords into chat.

## Invariants

- Never publish through this skill. Publishing requires a separately reviewed tool or explicit manual action.
- Stop when fewer than five distinct images or fewer than four inline images are supplied.
- Stop on authentication or upload failure.
- If `rank_math_rest_unavailable` is returned, keep the draft and explain that the site must expose the Rank Math fields through its REST API.
