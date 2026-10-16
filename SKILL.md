---
name: wp-draft-publisher
description: Write, revise, and save WordPress articles through the official REST API with draft-first publishing, structured HTML, media uploads, taxonomy assignment, and optional Rank Math metadata. Use for self-hosted WordPress article workflows.
---

# WP Draft Publisher

Use `scripts/run.ps1` for deterministic WordPress operations instead of browser automation when the REST API can complete the task.

## Workflow

1. Follow the site's editorial requirements and [references/article-format.md](references/article-format.md).
2. Choose the image count from the article's length and instructional needs. Long practical guides should have enough well-spaced inline images to avoid uninterrupted walls of text, without forcing a fixed count.
3. On a new site or after a permission change, run `scripts/run.ps1 doctor`. It is read-only.
4. Create a JSON payload using [references/payload-schema.md](references/payload-schema.md).
5. Use `scripts/run.ps1 dry-run --input <absolute-json-path>` when the user requests a preview, when checking a new site, or after changing payload-generation logic.
6. Close any WordPress editor tab for the target post, give the article a stable non-empty slug, then run `scripts/run.ps1 draft --input <absolute-json-path>`. An existing draft with that slug is updated in place.
7. Require `verification_status=verified`, then return the draft ID, preview URL, media count, and SEO status. Inspect the preview on desktop and mobile. Use `scripts/run.ps1 inspect --id <post-id>` for compact read-only verification.

The helper forces `status=draft`. It resolves or creates categories and tags, uploads media with alt text and captions, inserts valid figure markup at markers, sets the featured image, and attempts Rank Math metadata. Repeated creates update an existing draft with the exact slug. Byte-identical local images are reused by SHA-256 content hash. After every save, the post is read back and its title, slug, body, excerpt, featured image, categories, and tags must match before success is reported. Explicit minimums can be supplied through `image_policy` when needed.

Temporary read failures receive bounded retries. Writes are never blindly retried. On a definite failure, the helper rolls back only media created by the current operation and preserves reused attachments.

The helper performs complete local payload validation and read-only validation of referenced WordPress media before its first server mutation. Do not bypass preflight failures or substitute unvalidated direct API writes.

`dry-run` performs the same validation and reports planned post, media, taxonomy, and SEO actions with `would_mutate=false`. It may use authenticated GET requests but must never perform a mutating request.

## Existing drafts

Use `scripts/run.ps1 update-draft --id <post-id> --input <absolute-json-path>`. Reuse `media_id` values to avoid duplicate uploads. The helper verifies that the target still has `draft` status before any media or taxonomy mutation and refuses every other status. It never sends a status change when updating.

Do not leave the WordPress editor open during an API write. A stale browser autosave can overwrite the saved body. If read-back verification fails, close the editor and run `update-draft` once with the reviewed payload.

## Credentials

Run `scripts/setup-credentials.ps1` in an interactive Windows terminal. Credentials are encrypted with Windows DPAPI and stored outside the repository. Never request, print, commit, or paste application passwords into chat.

The helper accepts only HTTPS site URLs on port 443 and refuses redirects, embedded URL credentials, queries, fragments, and ambiguous URL characters. Do not bypass these checks.

## Invariants

- Never publish through this skill. Publishing requires a separately reviewed tool or explicit manual action.
- Stop when an explicit payload image policy is not satisfied.
- Stop on authentication or upload failure.
- If `rank_math_rest_unavailable` is returned, keep the draft and explain that the site must expose the Rank Math fields through its REST API.
- Prefer the included Draft Publisher REST Bridge when the user wants Rank Math automation and an atomic server-side draft-only update guard. Confirm it with `doctor`; never imply the bridge is active when `checks.bridge.ok` is false.
- Treat any write result without `verification_status=verified` as incomplete.
