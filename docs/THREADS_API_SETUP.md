# Threads API 발급 및 연결 체크리스트

이 자동화에 필요한 값은 최종적으로 두 가지입니다.

- `THREADS_ACCESS_TOKEN`: Threads API 호출용 액세스 토큰
- `THREADS_USER_ID`: 게시할 Threads 계정의 사용자 ID

AI 요약에는 둘 중 하나를 사용합니다.

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## 1. Meta 개발자 앱 만들기

1. [Meta for Developers](https://developers.facebook.com/)에 로그인합니다.
2. 새 앱을 생성합니다.
3. 앱 대시보드에서 Threads API 제품 또는 Threads 관련 사용 사례를 추가합니다.
4. 앱의 기본 설정에서 연락처 이메일, 개인정보처리방침 URL 등 필수 항목을 채웁니다.

## 2. 권한 준비

이 자동화는 다음 기능이 필요합니다.

- 공개 키워드 검색
- 내 Threads 계정으로 텍스트 게시

문서와 앱 대시보드에서 다음 계열 권한을 확인합니다.

- `threads_basic`
- `threads_content_publish`
- Threads keyword search 관련 권한 또는 기능

권한명이 문서/대시보드에서 다르게 표시될 수 있으므로, 공식 문서의 Keyword Search 페이지와 앱 리뷰 화면의 권한명을 우선합니다.

## 3. OAuth Redirect URI 설정

Meta 설정에서는 `localhost`, `127.0.0.1` 같은 로컬 주소가 허용되지 않을 수 있습니다.
따라서 Redirect URI에는 외부에서 접근 가능한 **HTTPS 공개 URL**을 등록해야 합니다.

사용 가능한 방식은 아래 중 하나입니다.

### 권장: 본인 도메인 사용

이미 소유한 도메인이나 배포 가능한 서버가 있다면 HTTPS URL을 하나 만듭니다.

예시:

```text
https://your-domain.com/threads/callback
```

이 URL을 Meta 앱의 Valid OAuth Redirect URIs에 등록합니다.

### 간단한 임시 방식: 터널링 HTTPS URL

개발 중에는 Cloudflare Tunnel, ngrok 같은 도구로 임시 HTTPS URL을 만들 수 있습니다.

예시:

```text
https://example-random-name.ngrok-free.app/callback
```

주의할 점:

- 무료 터널 URL은 재시작할 때 바뀔 수 있습니다.
- URL이 바뀌면 Meta 앱 설정의 Redirect URI도 다시 수정해야 합니다.
- 토큰 발급이 끝난 뒤 자동화 실행 자체에는 callback 서버가 계속 필요하지 않을 수 있습니다.

### 가장 간단한 방식: GitHub Pages 정적 콜백 페이지

토큰 발급 과정에서 리디렉션 URL에 붙은 `code`만 확인하면 되는 단계라면, GitHub Pages가 가장 간단합니다.
이 프로젝트에는 바로 배포할 수 있는 콜백 페이지가 `callback/index.html`로 포함되어 있습니다.

예시:

```text
https://your-github-id.github.io/thread_bot/callback/
```

진행 순서:

1. GitHub에 `thread_bot` 저장소를 만듭니다.
2. 이 프로젝트 파일을 저장소에 올립니다.
3. GitHub 저장소의 Settings > Pages로 이동합니다.
4. Source를 Deploy from a branch로 설정합니다.
5. Branch를 `main`, folder를 `/root`로 선택합니다.
6. Pages 배포가 끝나면 아래 주소를 Meta Redirect URI에 등록합니다.

```text
https://your-github-id.github.io/thread_bot/callback/
```

주의할 점:

- 저장소 이름이 다르면 URL의 `thread_bot` 부분도 바뀝니다.
- GitHub 사용자/조직 페이지 저장소를 쓰는 경우 URL 구조가 달라질 수 있습니다.
- Meta 앱에 등록한 Redirect URI와 실제 이동한 URL은 마지막 `/`까지 정확히 일치해야 합니다.
- 리디렉션 후 페이지에 표시되는 `code` 값을 복사해 토큰 교환 단계에 사용합니다.

## 4. 앱 모드와 테스트 사용자

앱이 개발 모드라면 본인 Threads 계정이 앱 역할 또는 테스트 사용자에 포함되어 있어야 합니다.
권한 요청 화면에서 본인 계정이 접근할 수 없으면 먼저 앱 대시보드에서 역할/테스터 설정을 확인합니다.

## 5. 액세스 토큰 발급

Meta Graph API Explorer 또는 앱 대시보드의 토큰 도구에서 Threads 권한을 포함한 사용자 액세스 토큰을 발급합니다.

개발 중에는 단기 토큰으로 먼저 연결을 확인하고, 상시 실행 전에는 장기 토큰 또는 갱신 가능한 운영 방식을 준비합니다.

## 6. 사용자 ID 확인

토큰 발급 후 Threads 사용자 ID를 확인합니다.

일반적으로 `/me` 또는 Threads API의 사용자 조회 엔드포인트로 확인합니다.
확인한 ID를 `THREADS_USER_ID`에 넣습니다.

## 7. 로컬 환경변수 설정

PowerShell 현재 창에서만 설정:

```powershell
$env:THREADS_ACCESS_TOKEN="발급받은_토큰"
$env:THREADS_USER_ID="Threads_사용자_ID"
$env:OPENAI_API_KEY="OpenAI_API_Key"
```

Gemini를 사용할 경우:

```powershell
$env:GEMINI_API_KEY="Gemini_API_Key"
```

## 8. 연결 테스트

토큰 연결 후 한 번만 실행합니다.

```powershell
thread-bot --config config.json run-once
```

초안이 생성되면 목록을 확인합니다.

```powershell
thread-bot --config config.json list-drafts
```

내용을 확인한 뒤 게시합니다.

```powershell
thread-bot --config config.json publish --draft-id 1
```

## 9. 30분 주기 실행

검증이 끝나면 다음 명령으로 계속 실행합니다.

```powershell
thread-bot --config config.json watch
```

PC 절전 모드에 들어가면 실행이 멈출 수 있으므로 전원/절전 설정을 확인합니다.
