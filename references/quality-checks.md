# Pre-save quality checks

Run `scripts/run.ps1 quality-check --input <absolute-json-path>` for a read-only report. `dry-run`, `draft`, and `update-draft` run the same checks automatically before the first mutation.

## Blocking structure checks

- No H1 inside the article body.
- H3 and lower headings require a preceding H2, and heading levels cannot be skipped.
- Every literal `<img>` has non-empty alt text. Payload images are separately required to have alt text.
- A present FAQ heading must contain question headings beneath it.

These are errors in both `warn` and `strict` modes.

## Recommendations

- Title and meta-description length.
- Focus keyword in the title and opening.
- Minimum existing internal links and duplicate/similar existing titles.
- Minimum recognized official-source links. Configure non-government official domains in `quality.official_domains`.
- Paragraph distance between inline images.
- The selected length-based image minimums are enforced by `image_policy`; an unmet minimum blocks before upload.
- HTTP external links.
- Fixed pixel/rem/em widths and `white-space:nowrap` that may overflow on mobile.
- A reminder to inspect every table in a mobile preview.
- Missing source records for time-sensitive articles, old check dates, expired deadlines, mismatched effective years, source links omitted from the article, and conflicting claims across sources.

Recommendations reduce the score. They block saving only in `strict` mode.

The report includes a `display` block intended for user interfaces. It gives a plain-language status, passed-check count, score, blocking and recommendation counts, and a suggested fix for every issue. Conflicting claims, expired source material, and structural errors are never silently auto-corrected.

Before validation, the helper may apply formatting-only safe fixes: trim outer whitespace, normalize repeated whitespace in SEO text, and remove fixed pixel/rem/em widths from literal image tags. Applied changes appear in `display.auto_fixes_applied`. It never guesses facts, resolves source conflicts, shortens editorial copy, creates links, or changes headings automatically.

Internal-link checks query WordPress posts and pages by slug. They do not send requests to arbitrary external sites. Mobile checks inspect markup and cannot replace a final browser preview with the active theme and plugins.

For a complete article, choose `image_policy.minimum_total` and `image_policy.minimum_inline` from the site profile or [article-format.md](article-format.md). The policy counts supplied media before any mutation, while the spacing check catches poor distribution. After saving, compare the verified media count and rendered figures with the plan so a successful upload cannot hide a missing marker or misplaced visual.
