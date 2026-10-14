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
  "seo": {
    "title": "SEO title",
    "description": "A concise and accurate meta description.",
    "focus_keyword": "focus keyword"
  }
}
```

For `featured_image` and each item in `inline_images`, an existing WordPress attachment `media_id` may be supplied instead of a new file `path`. The default guard requires at least five distinct images in total and at least four image markers in the body.
