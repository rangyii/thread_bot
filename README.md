# Threads 현장 요약 자동화

Threads 공개 키워드 검색 API로 현장 제보 글을 모아 30분마다 검토용 요약 초안을 생성합니다.
게시 전 확인을 전제로 하며, 자동 게시 대신 `publish` 명령을 별도로 실행합니다.

## 준비

1. Python 3.11 이상에서 패키지를 설치합니다.

```powershell
python -m pip install -e .
```

2. `config.json`의 키워드, 블랙리스트, 모델 설정을 필요에 맞게 수정합니다.
3. Threads API 권한 승인 후 환경변수를 설정합니다.

Threads API 발급 절차는 [docs/THREADS_API_SETUP.md](docs/THREADS_API_SETUP.md)를 참고합니다.

```powershell
$env:THREADS_ACCESS_TOKEN="..."
$env:THREADS_USER_ID="..."
$env:OPENAI_API_KEY="..."
```

Authorization code를 받은 직후에는 아래 명령으로 토큰을 교환할 수 있습니다.

```powershell
$env:THREADS_APP_ID="..."
$env:THREADS_APP_SECRET="..."
thread-bot --config config.json auth-url --redirect-uri "https://your-github-id.github.io/thread_bot/callback/"
thread-bot exchange-code --code "받은_authorization_code" --redirect-uri "https://your-github-id.github.io/thread_bot/callback/"
```

Gemini를 쓰려면 `config.json`의 `ai.provider`를 `gemini`로 바꾸고 다음을 설정합니다.

```powershell
$env:GEMINI_API_KEY="..."
```

## 실행

한 번만 수집하고 초안을 만들기:

```powershell
thread-bot --config config.json run-once --verbose
```

최근 45분 제한 때문에 비어 보이면 임시로 범위를 넓혀 확인할 수 있습니다.

```powershell
thread-bot --config config.json run-once --verbose --lookback-minutes 1440
```

특정 검색어만 API 연결 테스트:

```powershell
thread-bot --config config.json me-test
thread-bot --config config.json my-threads --limit 5
thread-bot --config config.json token-debug
thread-bot --config config.json search-test "올림픽공원"
thread-bot --config config.json search-test "올림픽공원" --search-type TOP
```

30분마다 계속 실행:

```powershell
thread-bot --config config.json watch
```

최근 초안 확인:

```powershell
thread-bot --config config.json list-drafts
thread-bot --config config.json show-draft --draft-id 1
thread-bot --config config.json recent-posts --limit 20
```

초안을 확인한 뒤 게시:

```powershell
thread-bot --config config.json publish --draft-id 1
```

게시 API는 공식 흐름대로 `POST me/threads`로 컨테이너를 만든 뒤 `POST me/threads_publish`로 게시합니다.

## 키워드 관리

검색 키워드는 `config.json`의 `keywords.include_groups`에 저장됩니다.
블랙리스트 키워드는 `keywords.blacklist_groups`에 저장됩니다.

현재 키워드 목록 보기:

```powershell
thread-bot --config config.json keywords list
```

검색 키워드 추가/삭제:

```powershell
thread-bot --config config.json keywords add-search "올림픽홀" --group 1
thread-bot --config config.json keywords remove-search "올림픽홀"
```

블랙리스트 키워드 추가/삭제:

```powershell
thread-bot --config config.json keywords add-blacklist "새 음모론 키워드" --group-name "음모론성 키워드"
thread-bot --config config.json keywords remove-blacklist "새 음모론 키워드"
```

기본 블랙리스트에는 `예수회`, `전사안`, `딥스`가 포함되어 있습니다.
개인 신원·신상 노출은 정규식 기반 필터와 블랙리스트 키워드를 함께 사용합니다.

## 로그

수집 원문, 필터링 사유, 생성 초안, 게시 기록은 SQLite 파일에 저장됩니다.
기본 경로는 `data/thread_bot.sqlite3`입니다.
