# 콘텐츠 계획 기능

`content-plan`은 WordPress 내용을 바꾸지 않는 읽기 전용 명령입니다. 전체 글과 카테고리를 페이지별로 불러와 다음 정보를 반환합니다.

- 글이 적은 카테고리 순서
- 제목이 지나치게 비슷한 기존 글 묶음
- Search Console 검색어별 새 글 또는 기존 글 보완 우선순위
- 관련 기존 글 ID를 이용한 내부 링크 후보
- `proposal_only`로 표시된 제안 일정

## Search Console 파일

Google Search Console의 **실적 → 검색결과 → 내보내기**에서 CSV를 내려받고 압축 파일이라면 CSV를 먼저 꺼냅니다. 최대 파일 크기는 10MB입니다. CSV와 JSON만 지원하며 파일 내용은 WordPress로 전송하지 않습니다.

CSV는 영문 `query, page, clicks, impressions, ctr, position` 또는 다음 한국어 열 이름을 인식합니다.

- 검색어, 인기 검색어, 상위 검색어
- 페이지, 인기 페이지, 상위 페이지
- 클릭수 또는 클릭
- 노출수 또는 노출
- CTR 또는 클릭률
- 게재순위 또는 순위

JSON은 같은 이름의 객체 배열, `rows` 배열, 또는 Search Console API처럼 `keys`, `clicks`, `impressions`, `ctr`, `position`을 가진 행을 지원합니다.

```powershell
scripts\run.ps1 --site 내블로그 content-plan --search-console "C:\보고서\검색결과.csv" --weeks 4 --per-week 2
```

같은 검색어가 여러 페이지에 있으면 클릭과 노출을 합치고 평균 순위를 노출수로 가중 계산합니다. 노출이 10회 미만인 검색어는 추천에서 제외합니다. 이 점수는 편집 우선순위를 돕는 지표이며 검색량 보장이나 자동 발행 지시가 아닙니다.
