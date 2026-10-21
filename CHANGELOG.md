# Changelog

All notable changes to WP Draft Publisher are recorded here. This project follows [Semantic Versioning](https://semver.org/).

## 1.0.0 - 2026-10-21

### Added

- Enforceable length-based image planning, marker verification guidance, and cohesive visual-sequence requirements for complete articles.
- A clean extracted-ZIP installation test and full release-candidate gate covering supported WordPress environments, checksums, deterministic packaging, and secret scanning.
- A Windows release workflow gate so GitHub cannot publish artifacts that fail first-use installation.
- One-command Windows installer with encrypted DPAPI credential storage and reusable editorial profiles.
- Safe WordPress draft creation and same-slug draft updates through the REST API.
- Featured and inline image upload, SHA-256 media reuse, categories, tags, and Gutenberg-compatible markup.
- Rank Math, Yoast SEO, AIOSEO, and native WordPress SEO fallback support.
- Structure, SEO, source, link, image, duplicate-title, and mobile-markup quality checks.
- Atomic draft-only updates, optimistic locking, private recovery snapshots, and privacy-safe activity records.
- Dependency-free stdio MCP server for Codex, Claude, Cursor, and compatible clients.
- Disposable real WordPress integration tests for WordPress 5.6/PHP 7.4 and current WordPress/PHP 8.3.
- Release ZIP, WordPress bridge ZIP, and SHA-256 checksum generation.
- A connection-first setup wizard that verifies WordPress before saving encrypted credentials and records non-secret site, taxonomy, SEO, bridge, and permission metadata.
- A `Tools → Draft Publisher` administrator screen with readiness checks, dedicated-user guidance, privacy-safe activity, and permission-checked draft recovery.
- A repeatable baseline command covering PowerShell parsing, Python compilation, plugin packaging, tests, and the public-file security scan.
- A versioned interactive editorial profile that reuses detected site language, categories, and SEO settings and preserves existing answers during edits.
- A read-only pre-save plan for the target draft, media, taxonomy, SEO, quality result, and safeguards.
- Freshness and source records with checked dates, effective-year and deadline validation, stale-source reminders, and blocking conflict detection.
- Live integration coverage for Rank Math, Yoast SEO, AIOSEO, native WordPress fallback, and simultaneous supported SEO plugins.
- Named multi-site profiles with isolated encrypted credentials, editorial settings, default-site selection, MCP session binding, and scoped removal.
- Read-only content planning across paginated WordPress inventory with category gaps, similar-title detection, internal-link candidates, and optional Search Console CSV/JSON opportunity scoring.

### Safety

- No publishing endpoint is exposed.
- Public, private, scheduled, pending, and trashed posts are protected from automated updates.
- Mutating requests are not blindly retried after uncertain responses.
- Saved drafts are read back and verified before success is reported.
