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
    "title": "SEO title",
    "description": "A concise and accurate meta description.",
    "focus_keyword": "focus keyword"
  }
}
```

For `featured_image` and each item in `inline_images`, an existing WordPress attachment `media_id` may be supplied instead of a new file `path`. Set `image_policy` only when the workflow requires explicit minimums. By default, one featured image is required and inline images are optional.
