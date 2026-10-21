# Content planning

`content-plan` is read-only. It paginates through the complete WordPress post and category inventory and returns category coverage, similar existing titles, new-versus-update opportunities, internal-link candidate IDs, and a proposal-only schedule.

An optional Search Console CSV or JSON export may be supplied. Files must be 10 MB or smaller. CSV recognizes the standard English headers `query`, `page`, `clicks`, `impressions`, `ctr`, and `position`, plus their common Korean export equivalents. JSON may be an array, a `rows` array, or Search Console API-style rows with `keys`, `clicks`, `impressions`, `ctr`, and `position`.

```powershell
scripts\run.ps1 --site my-blog content-plan --search-console "C:\reports\search-results.csv" --weeks 4 --per-week 2
```

Duplicate query rows are aggregated. Queries below ten impressions are excluded. The score is an editorial prioritization aid; it is not a search-volume guarantee. The file remains local, and this command never creates, updates, schedules, or publishes WordPress content.
