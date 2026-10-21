# User scenarios

## First draft

After installation, ask:

```text
Research the current eligibility and application process for a public benefit using official sources. Write a beginner-friendly article with images, FAQ, and SEO fields, then save it as a WordPress draft and verify the saved result.
```

The workflow reads the editorial profile, prepares the article and media, runs quality checks, shows a read-only pre-save plan, saves a draft, and reads it back for verification. The user reviews and publishes it manually.

## Review before saving

```text
Prepare an article about reducing travel exchange fees. Do not save it yet. Show the quality-check findings and planned WordPress changes first.
```

The AI uses quality-check and preview-plan operations without mutating WordPress.

## Update an existing draft

```text
Add a worked example and FAQ to the existing ETF beginner-guide draft. Update the same draft and do not create a duplicate.
```

The stable slug identifies the existing draft. Public or otherwise non-draft content is never updated.

## Concurrent human edit

If a person changes the draft after the AI reads it, optimistic locking stops the update with `post_changed_since_read`. The user can review the latest version and request a new merge.

## Restore a prior version

```text
Restore the draft I just changed to its previous snapshot.
```

Restoration is permission checked, limited to drafts, verified after completion, and creates a recovery point for the state it replaces.

## Other MCP clients

Claude Desktop, Cursor, and compatible stdio MCP clients can read the same editorial profile and run the same site discovery, doctor, quality, preview-plan, content-plan, draft, inspection, snapshot, restoration, and activity tools. No publish tool is exposed.

## Multiple blogs

Configure each site with a different profile key. A CLI command selects one with `--site company`; an MCP server entry selects one with `WPDP_SITE=company`. The pre-save plan reports the selected site profile and address. Stop before writing if either differs from the request.

## Four-week content plan

Export Search Console search results as CSV, then ask for a four-week plan with two articles per week. The tool reads complete WordPress inventory, reports category gaps and similar titles, and ranks new versus update opportunities with internal-link candidates. Every schedule entry is `proposal_only`; no post is created, updated, scheduled, or published.

## Stop using the tool

Uninstall the skill, remove local encrypted settings, revoke the WordPress Application Password, and optionally remove the bridge plugin. See `UNINSTALL.md`.
