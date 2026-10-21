# Draft payload

```json
{
  "title": "Article title",
  "slug": "article-slug",
  "excerpt": "A short summary for search results and the article header.",
  "content": "<p>Opening paragraph.</p>{{IMAGE_1}}<h2>Section</h2>{{IMAGE_2}}",
  "category_names": ["Guides"],
  "tag_names": ["How-to"],
  "featured_image": {
    "path": "C:/absolute/path/featured.png",
    "alt": "A concrete description of the image",
    "caption": "Optional caption"
  },
  "inline_images": [
    {
      "marker": "{{IMAGE_1}}",
      "path": "C:/absolute/path/step-1.png",
      "alt": "A concrete description of the image",
      "caption": "One sentence explaining what the image demonstrates"
    }
  ],
  "image_policy": {
    "minimum_total": 1,
    "minimum_inline": 0
  },
  "seo": {
    "provider": "auto",
    "title": "SEO title",
    "description": "A concise and accurate meta description.",
    "focus_keyword": "focus keyword"
  },
  "quality": {
    "mode": "warn",
    "minimum_internal_links": 1,
    "minimum_official_links": 1,
    "official_domains": ["gov.kr"],
    "require_faq": false,
    "require_source_records": true,
    "source_max_age_days": 45
  },
  "freshness": {
    "time_sensitive": true,
    "as_of": "2026-10-20",
    "effective_year": 2026
  },
  "source_records": [
    {
      "url": "https://www.gov.kr/example",
      "title": "Official program notice",
      "publisher": "Government agency",
      "checked_at": "2026-10-20",
      "published_at": "2026-09-01",
      "effective_year": 2026,
      "expires_on": "2026-12-31",
      "official": true,
      "claims": {"eligibility": "age 19-34", "income_limit": "120%"}
    }
  ]
}
```

For `featured_image` and each item in `inline_images`, an existing WordPress attachment `media_id` may be supplied instead of a new file `path`. For a complete article, set `image_policy` from the site's profile or the length bands in [article-format.md](article-format.md). The API's technical fallback requires only one featured image, so omitting the policy is suitable only for an intentionally text-first or user-requested low-visual workflow.

## Validation rules

- `title`, `content`, and all three `seo` values must be non-empty strings.
- `seo.provider` is optional: `auto`, `rank-math`, `yoast`, `aioseo`, or `none`. `auto` detects an active supported plugin. `none` uses the WordPress title and excerpt.
- Category and tag values must be non-empty and unique within their respective lists.
- Each image must provide exactly one source: a positive integer `media_id` or an absolute local `path`.
- Every image requires non-empty alt text.
- Local files must be non-empty JPEG, PNG, GIF, WebP, or AVIF images with a matching binary signature. SVG is not accepted.
- Inline markers must be unique and each marker must occur exactly once in `content`.
- Image policy values must be non-negative JSON integers, with `minimum_total` at least `1`.
- All local validation and read-only checks of referenced media finish before uploads or taxonomy creation begin.
- `freshness` and `source_records` are optional for evergreen articles. Set `time_sensitive=true` for benefits, tax, finance, deadlines, prices, laws, or other facts that can change.
- Source records require an HTTPS URL, title, publisher, ISO `checked_at` date, and `official` boolean. Optional dates also use `YYYY-MM-DD`.
- Conflicting values for the same claim, expired source records, future check dates, and effective-year mismatches block saving.

## Quality policy

`quality` is optional. The helper always checks heading order, body H1 use, image alt text, FAQ structure, internal links, similar existing titles, source links, image spacing, and fixed-width mobile overflow risks before a write.

- `mode`: `warn` (default) blocks structural errors and reports recommendations, while `strict` also blocks recommendations.
- Length settings: `title_min`, `title_max`, `meta_min`, and `meta_max`.
- Content minimums: `minimum_internal_links`, `minimum_official_links`, and `max_paragraphs_without_image`.
- Source settings: `require_source_records` and `source_max_age_days`.
- `official_domains`: domains that count as authoritative for this article. Korean government `.go.kr` and `gov.kr` links are recognized automatically.
- Feature switches: `require_faq`, `check_internal_links`, and `check_duplicate_titles`.

See [quality-checks.md](quality-checks.md) for the exact behavior and limitations.
