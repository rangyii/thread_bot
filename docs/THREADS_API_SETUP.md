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
5. 앱을 개시 또는 라이브 상태로 전환합니다.

앱 상태나 권한을 바꾼 뒤에는 기존 토큰을 계속 쓰지 말고 새 Authorization code와 새 Access Token을 발급받아야 합니다.

## 2. 권한 준비

이 자동화는 다음 기능이 필요합니다.

- 공개 키워드 검색
- 내 Threads 계정으로 텍스트 게시

`config.json`의 기본 요청 scope는 아래와 같습니다.

```json
["threads_basic", "threads_content_publish", "threads_keyword_search"]
```

Meta 대시보드나 공식 문서에 표시되는 정확한 권한명이 다르면 `config.json`의 `threads.scopes`를 그 이름에 맞게 수정합니다.

## 3. GitHub Pages Redirect URI

Meta 설정에서는 `localhost`, `127.0.0.1` 같은 로컬 주소가 허용되지 않을 수 있습니다.
따라서 Redirect URI에는 외부에서 접근 가능한 HTTPS 공개 URL을 등록해야 합니다.

이 프로젝트에는 GitHub Pages로 배포할 수 있는 콜백 페이지가 `callback/index.html`로 포함되어 있습니다.

예시:

```text
https://your-github-id.github.io/thread_bot/callback/
```

주의할 점:

- 저장소 이름이 다르면 URL의 `thread_bot` 부분도 바뀝니다.
- Meta 앱에 등록한 Redirect URI와 실제 이동한 URL은 마지막 `/`까지 정확히 일치해야 합니다.
- 리디렉션 후 페이지에 표시되는 `code` 값을 복사해 토큰 교환 단계에 사용합니다.

## 4. 권한 요청 URL 만들기

먼저 Meta 앱 대시보드에서 App ID와 App Secret을 확인한 뒤 PowerShell에 설정합니다.

```powershell
$env:THREADS_APP_ID="Meta_App_ID"
$env:THREADS_APP_SECRET="Meta_App_Secret"
```

그 다음 이 명령으로 권한 요청 URL을 만듭니다.

```powershell
thread-bot --config config.json auth-url --redirect-uri "https://your-github-id.github.io/thread_bot/callback/"
```

출력된 URL을 브라우저에 붙여넣고 승인합니다.
승인 후 GitHub Pages 콜백 페이지에 표시되는 Authorization code를 복사합니다.

## 5. Authorization code를 Access Token으로 교환

받은 `code`와 Meta에 등록한 Redirect URI를 그대로 넣어 실행합니다.

```powershell
thread-bot --config config.json exchange-code --code "받은_authorization_code" --redirect-uri "https://your-github-id.github.io/thread_bot/callback/"
```

이 명령은 내부적으로 다음 순서로 요청합니다.

1. `POST /oauth/access_token`: Authorization code를 short-lived access token으로 교환
2. `GET /access_token`: short-lived access token을 long-lived access token으로 교환

성공하면 아래처럼 출력됩니다.

```text
THREADS_ACCESS_TOKEN=...
THREADS_USER_ID=...
EXPIRES_IN_SECONDS=...
```

출력된 값을 현재 PowerShell 세션에 다시 설정합니다.

```powershell
$env:THREADS_ACCESS_TOKEN="출력된_access_token"
$env:THREADS_USER_ID="출력된_user_id"
```

주의할 점:

- Authorization code는 짧은 시간 동안만 유효하며, 한 번 사용하면 다시 사용할 수 없습니다.
- 앱 개시, 권한 추가, scope 변경 후에는 새 code와 새 token을 받아야 합니다.
- `redirect-uri` 값은 Meta 앱에 등록한 Redirect URI와 정확히 같아야 합니다.

## 6. 연결 테스트

먼저 Threads API에서 토큰이 기본적으로 유효한지 확인합니다.

```powershell
thread-bot --config config.json me-test
thread-bot --config config.json my-threads --limit 5
```

이 명령들이 성공하면 `threads_basic` 계열 토큰은 작동하는 것입니다.

현재 토큰에 어떤 scope가 들어있는지 확인하려면 아래 명령을 실행합니다.

```powershell
thread-bot --config config.json token-debug
```

출력에서 `threads_keyword_search`가 보여야 공개 키워드 검색을 호출할 수 있습니다.
다만 Meta `debug_token` endpoint가 Threads 앱 정보를 읽지 못하는 경우가 있을 수 있으므로, `token-debug`가 실패하고 `me-test`가 성공하면 `/me` 결과를 우선 기준으로 삼고 Keyword Search를 직접 테스트합니다.

먼저 검색 API 권한을 확인합니다.

```powershell
thread-bot --config config.json search-test "올림픽공원"
thread-bot --config config.json search-test "올림픽공원" --search-type TOP
```

성공하면 한 번만 전체 수집을 실행합니다.

```powershell
thread-bot --config config.json run-once
```

초안이 생성되면 목록을 확인합니다.

```powershell
thread-bot --config config.json list-drafts
thread-bot --config config.json show-draft --draft-id 1
thread-bot --config config.json recent-posts --limit 20
```

내용을 확인한 뒤 게시합니다.

```powershell
thread-bot --config config.json publish --draft-id 1
```

게시 시 `Object with ID 'username' does not exist` 같은 오류가 나오면 `THREADS_USER_ID`에 username이 들어간 것입니다.
현재 코드는 공식 문서 흐름대로 `POST me/threads`와 `POST me/threads_publish`를 사용하므로 게시에는 `THREADS_USER_ID`가 필요하지 않습니다.

## 7. Keyword Search 권한 오류

검색 테스트에서 아래와 같은 오류가 나오면 토큰은 있지만 공개 키워드 검색 권한이 없는 상태입니다.

```text
Application does not have permission for this action
code: 10
```

확인할 항목:

- 앱이 개시 또는 라이브 상태인지 확인합니다.
- Threads API 제품이 앱에 추가되어 있는지 확인합니다.
- `threads_keyword_search` 또는 Meta 대시보드에 표시되는 Keyword Search 권한이 앱에 부여되어 있는지 확인합니다.
- 권한 변경 후 새 Authorization code와 새 Access Token을 발급합니다.
- 앱 리뷰가 필요한 권한이라면 리뷰 승인 전까지 제한될 수 있습니다.
- `thread-bot --config config.json token-debug` 출력에 `threads_keyword_search`가 실제로 들어있는지 확인합니다.

## 8. 30분 주기 실행

검증이 끝나면 다음 명령으로 계속 실행합니다.

```powershell
thread-bot --config config.json watch
```

PC 절전 모드에 들어가면 실행이 멈출 수 있으므로 전원/절전 설정을 확인합니다.
