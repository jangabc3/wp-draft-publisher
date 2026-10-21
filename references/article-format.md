# Default article format

Apply the site's own editorial guide when one exists. Otherwise:

- Answer the search intent directly in the opening paragraph.
- Supply the page H1 through the WordPress title. Start body sections at H2; reserve H3 for subsections.
- Prefer concrete steps, checklists, comparison tables, troubleshooting guidance, and a focused FAQ. Structure FAQ items as semantic H3 questions followed immediately by paragraph answers so the site's stylesheet can format every pair consistently.
- Use valid semantic HTML.
- Insert images as `<figure class="wp-block-image size-large">` containing an `<img>` with useful alt text and, when helpful, a `<figcaption>`. Never wrap images in headings.
- Add only relevant internal links. When suitable, group two or more of them in a clear related-reading section near the end.
- Cite direct official guidance pages for changing or consequential facts. Do not add generic date-stamped editorial boilerplate when the date does not help the reader.
- End with a concise practical recap.
- Use an accurate SEO title, a useful meta description, and one natural focus keyword.
- Count visible body characters after removing HTML tags, image markers, and whitespace. Unless the site profile or user requests another density, use the following minimums and record them in `image_policy`:

| Visible body length | Featured | Inline | Total |
| --- | ---: | ---: | ---: |
| Up to 1,500 characters | 1 | 2 | 3 |
| 1,501-2,499 characters | 1 | 3 | 4 |
| 2,500-4,000 characters | 1 | 4 | 5 |
| 4,001-5,500 characters | 1 | 5 | 6 |
| Over 5,500 characters | 1 | 5, plus one per additional 1,500 characters | 6+ |

- Give each image a purpose in the outline before generating or selecting it. A four-image inline sequence commonly covers orientation, comparison or calculation, action steps, and mistakes or a final checklist.
- Place each image immediately after the content it explains. Do not place images back-to-back, cluster them near the opening, repeat the featured composition, or leave more than two substantial H2 sections without a visual when the selected length band calls for one.
- Before saving, count `inline_images`, verify that every marker occurs exactly once, and keep `image_policy.minimum_total` and `image_policy.minimum_inline` equal to the selected minimums. After saving, confirm that the rendered draft contains the same number of inline figures.
- Use descriptive alt text that states both the visible subject and its nearby purpose. Add a caption only when it supplies interpretation or an action reminder.
- Unless the site's editorial guide requests another style, use a cohesive set of bright, premium, photorealistic editorial images with realistic materials, clean composition, and a strong subject that remains clear at mobile thumbnail size. Keep embedded text, letters, numbers, logos, and watermarks out of generated images by default.
- Save as a draft.
