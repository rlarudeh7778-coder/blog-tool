# 워드프레스 완전 자동 발행 (손 안 대는 자동화)

매일 GitHub Actions(서버)가 자동으로 **글 생성 → 워드프레스 발행**까지 합니다.
사람이 도구를 열거나 클릭할 필요가 전혀 없습니다. (티스토리처럼 복붙 X)

- **IT 정보글 위주** + 설정한 주기(`phone_every`)마다 **선불폰 글 자동 삽입**
- 참고 자료(references)를 넣으면 **사실만 참고하고 문장은 100% 새로 각색**(유사도/표절 방지)
- B스타일·모바일 최적화 HTML + 선불폰 글엔 메이플통신 CTA·접속버튼·구조화데이터 자동

---

## 0. 먼저 필요한 것
1. **워드프레스 사이트** (자체 호스팅 = wordpress.org. 도메인+호스팅)
2. **Claude API 키** (console.anthropic.com)

> 아직 워드프레스가 없으면 → 시크릿(WP_*) 없이 둬도 됩니다. 그러면 자동으로 **DRY_RUN**(발행 안 하고 `scripts/preview/`에 미리보기 HTML만 생성)으로 돌아가서, 글 품질만 미리 확인할 수 있어요.

## 1. 워드프레스 응용 프로그램 비밀번호 발급
1. 워드프레스 관리자 → **사용자 → 프로필**
2. 맨 아래 **응용 프로그램 비밀번호(Application Passwords)** → 이름 입력(예: autopost) → 생성
3. 표시되는 비밀번호(`xxxx xxxx xxxx xxxx`) 복사 (공백 포함 그대로)

## 2. GitHub 시크릿 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키 (`sk-ant-...`) |
| `WP_URL` | 워드프레스 주소 (예: `https://내도메인.com`) |
| `WP_USER` | 워드프레스 로그인 아이디 |
| `WP_APP_PASSWORD` | 위에서 발급한 응용 프로그램 비밀번호 |

## 3. 무엇을 쓸지 정하기 — `scripts/autopost_config.json`
- `it_topics`: IT 글 주제 목록 (계속 추가 가능)
- `phone_keywords`: 선불폰 글 키워드(지역+선불폰, 브랜드 등)
- `phone_every`: 몇 편마다 선불폰 1편 넣을지 (기본 5 = IT 4편 + 선불폰 1편)
- `posts_per_run`: 한 번 실행에 몇 편 발행할지 (기본 1)
- `references`: 참고할 글 내용 붙여넣기 (있으면 각색, 없으면 주제만으로 생성)
- `contact` / `platform_url`: 선불폰 CTA·접속버튼 정보 (이미 메이플통신으로 세팅됨)

**참고 자료 넣는 법** (선택):
```json
"references": [
  { "title": "메모", "text": "참고 블로그 글 본문을 여기 붙여넣기..." }
]
```

## 4. 실행 / 확인
- **수동 실행**: Actions 탭 → **"워드프레스 자동 발행" → Run workflow**
  - `dry_run`에 `1` 넣으면 발행 안 하고 미리보기만 (품질 확인용)
- **자동 실행**: 매일 10:00(KST). 빈도/개수는 `autopost.yml`의 cron과 `posts_per_run`으로 조절
- 발행 이력은 `scripts/autopost_state.json`에 기록되어 **같은 주제 중복 없이** 다음 것부터 이어서 발행됩니다.

> ⚠️ cron 자동 실행은 GitHub 규칙상 **기본 브랜치(main)** 에서만 됩니다. 이 기능을 main에 머지해야 매일 자동 발행이 켜집니다.

## 5. 발행량 늘리기
- 새 워드프레스 도메인이면 처음 1~2주는 `posts_per_run: 1`로 천천히
- 색인이 잘 잡히면 `posts_per_run`을 2~3으로 올리거나 cron을 하루 여러 번으로

## 안전장치
- WP 시크릿이 하나라도 없으면 자동 DRY_RUN(절대 아무 데도 발행 안 함)
- 한 글 실패해도 전체가 죽지 않고 다음 글로 진행
- 참고 자료는 "사실 확인용"으로만 쓰도록 프롬프트에 강제(원문 복사 금지)
