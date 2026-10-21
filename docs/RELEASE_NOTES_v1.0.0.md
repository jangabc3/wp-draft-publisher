# WP Draft Publisher v1.0.0

The first public release turns a natural-language article request into a reviewable WordPress draft while keeping final publication under human control.

## Highlights

- Double-click Windows installation with encrypted local credentials and a reusable editorial profile.
- Draft creation and same-slug draft updates with featured images, inline images, categories, and tags.
- Rank Math, Yoast SEO, AIOSEO, and native WordPress SEO fallback support.
- Pre-save quality checks for structure, links, official sources, images, duplicate titles, FAQ markup, and mobile display risks.
- Atomic draft-only updates, human-edit conflict detection, recovery snapshots, and privacy-safe activity history.
- stdio MCP support for Codex, Claude, Cursor, and compatible clients.
- Multiple named WordPress sites with isolated encrypted credentials and editorial profiles.
- Read-only four-week content planning from category gaps, similar titles, internal-link candidates, and optional Search Console exports.
- English and Korean installation, removal, and scenario documentation.

## Install

1. Download `wp-draft-publisher-v1.0.0.zip` and `SHA256SUMS.txt`.
2. Verify the ZIP checksum.
3. Extract the ZIP and double-click `install.cmd`.
4. Optionally install `draft-publisher-rest-bridge.zip` in WordPress for the full safety and SEO feature set.

## Verified environments

- WordPress 5.6 with PHP 7.4: core draft workflow.
- Current WordPress with PHP 8.3: core workflow, native fallback, Rank Math, Yoast, AIOSEO, and simultaneous-plugin selection.
- Python 3.9 and 3.13 on Windows and Ubuntu: unit test matrix.

## Safety boundary

The project has no publishing operation. It refuses to update non-draft posts, stops stale overwrites, verifies saved content, and keeps credentials outside the repository.
