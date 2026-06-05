# 레퍼런스 자동 수집 설정 (한 번만 하면 끝)

매일 새벽 GitHub Actions가 자동으로 유튜브·레딧·구글트렌드에서 레퍼런스를 모아
`data.json`을 갱신합니다. **딱 한 가지**, 유튜브 API 키만 등록하면 동작합니다.

## 1. 유튜브 API 키 발급 (무료)

1. https://console.cloud.google.com 접속 → 프로젝트 하나 생성
2. 좌측 **API 및 서비스 → 라이브러리** → "YouTube Data API v3" 검색 → **사용 설정**
3. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키**
4. 생성된 키(`AIza...`) 복사

## 2. GitHub 시크릿에 등록

1. 이 저장소 → **Settings → Secrets and variables → Actions**
2. **New repository secret** 클릭
3. Name: `YOUTUBE_API_KEY` / Secret: 위에서 복사한 키 붙여넣기 → 저장

## 3. 끝 — 동작 확인

- **Actions 탭 → "레퍼런스 자동 수집" → Run workflow** 로 지금 바로 한 번 실행해 볼 수 있어요.
- 이후엔 매일 06:00(KST) 자동 실행되어 `data.json`을 갱신·커밋합니다.

> ⚠️ 예약 실행(cron)은 GitHub 규칙상 **기본 브랜치(main)** 에서만 돕니다.
> 이 기능이 들어간 브랜치를 main에 머지해야 매일 자동 수집이 켜집니다.

## 무엇을 수집하나

| 소스 | 내용 | 비고 |
|------|------|------|
| 유튜브 | 카테고리별 인기 영상(조회·좋아요·댓글 수 포함) | 공식 API, 안정적 |
| 구글 트렌드 | 그날 트렌드 키워드 → 유튜브 검색에 반영 | `#트렌드` 태그, best-effort |
| 레딧 | 카테고리별 인기 이미지 게시물 | 공개 API |

**인스타그램·페이스북 제외 이유:** '남들 인기 게시물 검색' 공식 API가 없고,
자동 수집이 약관으로 금지되어 있습니다. 꼭 필요하면 Apify 같은 유료 스크래퍼를
`collect.py`에 별도 연동해야 합니다(비용·약관 리스크 감수).

## 수집 범위 바꾸기

`scripts/collect.py` 상단의 `CATEGORIES`(검색어/서브레딧)와
`MAX_PER_CAT_YT`, `MAX_PER_CAT_REDDIT`, `DAYS_BACK` 숫자를 고치면 됩니다.
