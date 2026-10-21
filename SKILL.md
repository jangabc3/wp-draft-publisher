---
name: wp-draft-publisher
description: Write, revise, quality-check, and save WordPress articles through the official REST API with draft-first publishing, structured HTML, media uploads, taxonomy assignment, and Rank Math, Yoast, or AIOSEO metadata. Use for self-hosted WordPress article workflows.
---

# WP Draft Publisher

Use `scripts/run.ps1` for deterministic WordPress operations instead of browser automation when the REST API can complete the task.

The same Python workflow is available through `scripts/mcp_server.py` for stdio MCP clients. Codex should use this skill's CLI commands; Claude, Cursor, and compatible clients can launch `scripts/run-mcp.ps1` after the same credential setup.

## Workflow

1. Run `scripts/list-sites.ps1`. If the user names a site, pass `--site <key>` to every `run.ps1` command and `-Site <key>` to profile commands. If several sites exist and the request does not identify one, use the configured default only when the request and preview clearly match it; otherwise ask which site before any write. Never combine credentials, profiles, categories, or media across sites.
2. Run `scripts/show-profile.ps1 -Site <key>`. Apply the configured language, audience, tone, article length, image style, FAQ, internal-link, official-source, and SEO preferences. If the profile is missing, follow the site's stated requirements and [references/article-format.md](references/article-format.md), and recommend `scripts/setup-profile.ps1 -Site <key>` after completing the current request.
3. Plan the visual sequence before writing. Unless the site's profile or the user requests another density, apply the length bands in [references/article-format.md](references/article-format.md), set both `image_policy.minimum_total` and `image_policy.minimum_inline`, and give every planned image a distinct explanatory purpose. Never lower the policy because image preparation is inconvenient.
4. On a new site or after a permission change, run `scripts/run.ps1 [--site <key>] doctor`. It is read-only.
5. Create a JSON payload using [references/payload-schema.md](references/payload-schema.md). For time-sensitive benefits, tax, finance, deadline, price, or legal content, include `freshness` and `source_records` with official URLs, checked dates, effective years, deadlines, and claim values. Stop when official sources conflict or the applicable period has expired.
6. Run `scripts/run.ps1 [--site <key>] quality-check --input <absolute-json-path>` when revising content, then run `scripts/run.ps1 [--site <key>] preview-plan --input <absolute-json-path>` before every save. Both are read-only. Surface the concise plan: target site and site profile, target draft, categories, image upload/reuse count, SEO provider, quality result, and draft-only safeguards. When the user's request already authorizes saving, continue after a matching plan; stop for confirmation only when the target site/post differs or the plan reveals a material conflict. Follow [references/quality-checks.md](references/quality-checks.md).
7. Close any WordPress editor tab for the target post, give the article a stable non-empty slug, then run `scripts/run.ps1 [--site <key>] draft --input <absolute-json-path>`. An existing draft with that slug is updated in place.
8. Require `verification_status=verified` and `quality_status=passed`, then return the draft ID, preview URL, media count, SEO provider/status, and the quality `display` result with concrete fixes for remaining recommendations. Confirm that the verified inline-media count meets the planned length band and that the rendered figures are distributed through the article. Inspect the preview on desktop and mobile. Use `scripts/run.ps1 [--site <key>] inspect --id <post-id>` for compact read-only verification.

For content-calendar requests, run `scripts/run.ps1 [--site <key>] content-plan` with the user's Search Console CSV/JSON export when supplied. Treat every returned date as a proposal and never create, schedule, update, or publish posts from this planning command. Follow [references/content-planning.md](references/content-planning.md).

Bridge version 1.2.0 or later creates a private recovery snapshot before every guarded draft update. Use `scripts/run.ps1 snapshots --id <post-id>` to list recovery points. Run `scripts/run.ps1 restore-snapshot --snapshot-id <id>` only when the user explicitly asks to restore that draft. Restoration never applies to a published or otherwise non-draft post.

Bridge version 1.3.0 or later records privacy-safe operation metadata. Use `scripts/run.ps1 activity --limit 50` only when the user asks to inspect recent automated changes. The log contains IDs and status, never credentials, prompts, or article body content.

The helper forces `status=draft`. It resolves or creates categories and tags, uploads media with alt text and captions, inserts valid figure markup at markers, sets the featured image, and saves SEO fields through Rank Math, Yoast SEO, or AIOSEO. When none is active it uses the native WordPress title and excerpt fallback. Repeated creates update an existing draft with the exact slug. Byte-identical local images are reused by SHA-256 content hash. After every save, the post is read back and its title, slug, body, excerpt, featured image, categories, and tags must match before success is reported. Explicit minimums can be supplied through `image_policy` when needed.

Temporary read failures receive bounded retries. Writes are never blindly retried. On a definite failure, the helper rolls back only media created by the current operation and preserves reused attachments.

The helper performs complete local payload validation and read-only validation of referenced WordPress media before its first server mutation. Do not bypass preflight failures or substitute unvalidated direct API writes.

`preview-plan` and its `dry-run` alias perform the same validation and report planned post, media, taxonomy, SEO, quality, and safeguards with `would_mutate=false`. They may use authenticated GET requests but must never perform a mutating request.

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
- If `seo_bridge_unavailable` is returned, keep the draft and explain that bridge 1.4.1 or later is required for the selected SEO plugin.
- Prefer the included Draft Publisher REST Bridge for multi-plugin SEO automation and the atomic server-side draft-only update guard. Confirm it with `doctor`; never imply the bridge is active when `checks.bridge.ok` is false.
- Treat any write result without `verification_status=verified` as incomplete.
