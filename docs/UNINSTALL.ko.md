# 제거 및 접근 권한 폐기

## 1. Codex 스킬 제거

압축을 풀었던 원본 폴더에서 다음 명령을 실행합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1
```

이 명령은 `%USERPROFILE%\.codex\skills\wp-draft-publisher`만 제거합니다. 암호화된 연결 설정과 글쓰기 프로필은 유지합니다.

로컬 설정까지 모두 제거하려면 다음 명령을 실행합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1 -RemoveCredentials
```

삭제 대상은 `%LOCALAPPDATA%\WPDraftPublisher`입니다.

한 사이트만 제거하려면 `scripts\remove-site.ps1 -Site "사이트별칭"`을 실행합니다. 이 명령은 선택한 사이트의 로컬 자격증명과 프로필만 제거하며 확인을 요구합니다. 해당 WordPress의 애플리케이션 비밀번호도 별도로 폐기해야 합니다.

## 2. WordPress 애플리케이션 비밀번호 폐기

WordPress 관리자에서 자동화 전용 사용자의 프로필을 엽니다. **애플리케이션 비밀번호** 목록에서 `WP Draft Publisher`를 찾아 폐기합니다. 로컬 프로그램만 삭제해도 이미 발급한 WordPress 비밀번호는 자동으로 폐기되지 않으므로 이 과정이 필요합니다.

## 3. WordPress 브리지 제거

더 이상 스냅샷과 활동 기록이 필요하지 않다면 **플러그인 → 설치한 플러그인**에서 Draft Publisher REST Bridge를 비활성화하고 삭제합니다.

플러그인을 삭제하기 전에 필요한 임시글과 복원 지점이 있는지 확인하세요. 글과 업로드된 미디어 자체는 플러그인을 삭제해도 WordPress에 남습니다.

## 4. Claude·Cursor MCP 설정 제거

해당 프로그램의 MCP 설정에서 `wp-draft-publisher` 항목을 삭제하고 프로그램을 다시 시작합니다.
