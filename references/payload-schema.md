# Draft payload

```json
{
  "title": "글 제목",
  "slug": "english-slug",
  "excerpt": "검색 결과와 글 상단에 사용할 짧은 설명",
  "content": "<p>본문</p>{{IMAGE_1}}<h2>...</h2>{{IMAGE_2}}...",
  "category_names": ["생활경제"],
  "tag_names": ["핵심 태그"],
  "featured_image": {
    "path": "C:/absolute/path/featured.png",
    "alt": "구체적인 이미지 설명",
    "caption": "선택 사항"
  },
  "inline_images": [
    {
      "marker": "{{IMAGE_1}}",
      "path": "C:/absolute/path/step-1.png",
      "alt": "구체적인 이미지 설명",
      "caption": "이미지가 설명하는 내용을 한 문장으로 작성"
    }
  ],
  "seo": {
    "title": "SEO 제목",
    "description": "120~160자 안팎의 메타 설명",
    "focus_keyword": "핵심 키워드"
  }
}
```

`featured_image`와 각 `inline_images`에는 새 파일의 `path` 대신 기존 WordPress 첨부파일의 `media_id`를 사용할 수 있다. 총 다섯 개 이상의 서로 다른 이미지가 필요하며 본문에는 네 개 이상의 이미지 마커가 있어야 한다.
