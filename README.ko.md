# WP Draft Publisher

Codex, Claude, Cursor 같은 AI와 WordPress를 연결해 조사한 글을 **검토 가능한 임시글**로 저장하는 콘텐츠 자동화 도구입니다.

공개 전 전체 검증 결과와 GitHub에서만 할 수 있는 마지막 작업은 [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md)에 정리되어 있습니다. 유지관리자는 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-release-candidate.ps1`로 배포 후보 전체 검사를 한 번에 실행할 수 있습니다.

사용자가 “전세보증보험 가입 조건을 조사해서 글을 작성하고 워드프레스에 임시저장해줘”라고 요청하면 다음 작업을 한 흐름으로 처리합니다.

- 사이트의 글쓰기 규칙 확인
- 제목·본문·FAQ·공식 출처 구성
- 대표 이미지와 본문 이미지 배치
- 카테고리·태그 지정
- Rank Math·Yoast·AIOSEO 또는 WordPress 기본 SEO 정보 저장
- 글 구조와 링크, 출처, 이미지, 모바일 표시 품질검사
- 날짜에 민감한 글의 공식 출처·확인일·시행연도·마감일 검사와 출처 간 조건 충돌 차단
- 통과 항목, 차단 문제, 권장 수정과 해결 방법을 보여주는 품질 결과
- 글의 의미를 바꾸지 않는 공백과 이미지 고정 너비 자동 정리
- 저장 전에 대상 사이트·카테고리·이미지·SEO·품질 결과 미리보기
- WordPress 임시글 저장 후 서버 내용을 다시 읽어 검증
- 여러 WordPress 사이트의 연결 정보와 글쓰기 규칙을 서로 분리해 관리
- 카테고리 부족분·유사 글·내부 링크 후보와 Search Console 성과를 이용한 읽기 전용 콘텐츠 계획

자동 공개 기능은 제공하지 않습니다. 사용자가 WordPress에서 결과를 검토한 뒤 직접 공개합니다.

## 5분 설치

### 준비물

- Windows 10 또는 11
- Python 3.9 이상
- Codex
- HTTPS가 적용된 WordPress 5.6 이상
- 글과 미디어를 만들 수 있는 WordPress 전용 사용자와 애플리케이션 비밀번호

### 설치

1. GitHub Releases에서 `wp-draft-publisher-v1.0.3.zip`을 내려받아 압축을 풉니다.
2. 폴더 안의 `install.cmd`를 두 번 클릭합니다.
3. 안내에 따라 WordPress 주소, 사용자 이름, 애플리케이션 비밀번호를 입력합니다. 연결 검사가 성공하기 전에는 비밀번호를 저장하지 않습니다.
4. 자동 감지된 사이트 언어, 카테고리, SEO 플러그인과 계정 권한을 확인합니다.
5. 자동 감지된 값을 기본값으로 사이트 주제, 글의 말투, 독자층, 길이, 이미지 스타일, FAQ와 내부 링크 규칙을 입력합니다. 기존 프로필을 다시 실행하면 이전 답변이 유지됩니다.
6. 설치가 끝나면 Codex에서 새 채팅을 엽니다.
7. 다음처럼 요청합니다.

```text
청년 월세 지원 조건을 최신 공식 자료로 조사해서 완성도 높은 글을 만들고 워드프레스에 임시저장해줘.
```

애플리케이션 비밀번호는 현재 Windows 사용자만 해독할 수 있도록 DPAPI로 암호화되며 공개 프로젝트 폴더에 저장되지 않습니다.

WordPress에서는 **도구 → Draft Publisher**에서 서버 준비 상태, 전용 사용자 설정 안내, 최근 활동과 복원 지점을 확인할 수 있습니다.

글을 저장하기 전에는 읽기 전용 계획이 먼저 실행됩니다. 새 글인지 기존 임시글 수정인지, 카테고리, 새로 올릴 이미지와 재사용할 이미지 수, SEO 플러그인, 품질 점수, 임시글 보호 상태를 확인한 뒤 요청과 일치하면 저장합니다. 이 미리보기는 WordPress 내용을 변경하지 않습니다.

자세한 설치 과정은 [한국어 설치 안내](docs/INSTALL.ko.md), 실제 사용 예시는 [사용자 시나리오](docs/USER-SCENARIOS.ko.md)를 참고하세요.

## 여러 블로그와 콘텐츠 계획

두 번째 블로그를 추가할 때는 설치된 폴더에서 다음 명령을 실행합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-credentials.ps1" -ProfileName "회사블로그"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\setup-profile.ps1" -Site "회사블로그"
```

`list-sites.ps1`로 연결 목록을 확인하고 `set-default-site.ps1 -Site "회사블로그"`로 기본 블로그를 바꿀 수 있습니다. 명령별로 선택하려면 `run.ps1 --site 회사블로그 doctor`처럼 사용합니다. 각 사이트의 암호화된 자격증명, 글쓰기 프로필, 감지 정보는 별도 폴더에 보관됩니다.

콘텐츠 계획은 WordPress의 전체 글·카테고리를 읽어 부족한 카테고리, 유사 제목, 내부 링크 후보를 확인합니다. Search Console CSV 또는 JSON을 추가하면 노출수, 클릭률, 평균 순위를 바탕으로 새 글과 기존 글 개선 우선순위를 제안합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\wp-draft-publisher\scripts\run.ps1" --site 회사블로그 content-plan --search-console "C:\보고서\검색결과.csv" --weeks 4 --per-week 2
```

이 기능은 제안 일정만 만들며 글을 생성하거나 예약·공개하지 않습니다. 지원 형식은 [콘텐츠 계획 안내](references/content-planning.ko.md)에 정리되어 있습니다.

## 안전 기능

- 같은 슬러그의 임시글은 중복 생성하지 않고 기존 임시글을 갱신합니다.
- 공개·예약·비공개·검토 대기·휴지통 글은 자동 수정하지 않습니다.
- 사람이 글을 수정했다면 오래된 자동화 결과로 덮어쓰지 않습니다.
- 수정 전 서버 스냅샷을 저장해 이전 상태로 복원할 수 있습니다.
- 저장이 끝나면 제목, 본문, 이미지, 분류를 다시 읽어 일치 여부를 검증합니다.
- Rank Math·Yoast·AIOSEO가 함께 설치돼도 요청한 SEO 플러그인의 값을 다시 읽어 검증합니다.
- 비밀번호, 프롬프트, 글 전체 본문을 활동 기록에 남기지 않습니다.

## 지원 환경

기본 설치 프로그램은 Windows용입니다. MCP 서버 핵심 코드는 Python 표준 라이브러리만 사용하며, macOS·Linux에서는 운영체제의 비밀 저장 수단으로 환경 변수를 제공해 실행할 수 있습니다.

영문 전체 문서는 [README.md](README.md)를 참고하세요.

## 제거

프로그램 제거와 WordPress 접근 권한 폐기는 별개의 작업입니다. [한국어 제거 안내](docs/UNINSTALL.ko.md)에 따라 설치 폴더, 암호화된 로컬 설정, WordPress 애플리케이션 비밀번호를 순서대로 정리하세요.

## 라이선스

핵심 프로젝트는 MIT License입니다. WordPress 브리지 플러그인은 소스에 표시된 GPL-2.0-or-later 조건을 따릅니다.
