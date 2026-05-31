# 🔮 운명을 읽다 · AI 사주명리 (독립 사업체)

**블로그 도구와 완전히 분리된 독립 사이트**입니다. 두 개의 화면으로 구성됩니다.

| 파일 | 용도 | 공개 여부 |
|------|------|-----------|
| `index.html` | **고객용 판매 랜딩 페이지** (서비스 소개·가격·신청) | 공개 |
| `admin.html` | **운영자 전용 분석 도구** (만세력 계산 + AI 10파트 리포트 생성) | 운영자만 사용 |
| `.nojekyll` | GitHub Pages가 파일을 그대로 서빙 | — |

> 고객은 `index.html`(랜딩)만 봅니다. 운영자는 `.../admin.html`에서 Claude API 키를
> 한 번 저장한 뒤 분석을 생성해 PDF로 고객에게 전달합니다. **고객은 API 키가 필요 없습니다.**

---

## 사업 흐름 (반자동)

1. 고객이 랜딩(`index.html`)에서 **카카오톡/이메일**로 생년월일시·패키지 신청
2. 외부 결제(카카오페이·토스 등 **결제 링크**)로 입금 확인
3. 운영자가 `admin.html`에서 **사주판 계산 → 프리미엄 분석 생성**
4. **PDF/이미지**로 저장해 카톡·메일로 전달

---

## 배포 전 꼭 수정할 곳 (`index.html`)

- **신청 버튼 링크**: `<section id="apply">` 안의
  - `id="kakao"` 버튼 `href="#"` → 실제 **카카오톡 채널/네이버폼/인스타 DM** 링크로 교체
  - 이메일 버튼은 `rlarudeh7778@gmail.com`로 미리 채워져 있음 (원하면 변경)
  - 주석 `▼▼ 운영자: ... ▼▼` 사이를 찾으면 됩니다
- **가격**: `<section id="price">`의 금액(19,000 / 39,000 / 49,000)은 예시 → 자유롭게 수정
- **상호/문구**: 상단 `운명을 읽다` 브랜드명, 히어로 카피 등 취향대로

---

## 1) 새 GitHub 저장소로 독립 운영

1. GitHub에서 **새 저장소** 생성 (예: `saju-myeongri`)
2. 이 폴더 안의 파일을 새 저장소 루트에 올립니다: `index.html`, `admin.html`, `.nojekyll`

```bash
git clone https://github.com/<아이디>/saju-myeongri.git
cd saju-myeongri
cp /경로/blog-tool/saju-site/index.html .
cp /경로/blog-tool/saju-site/admin.html .
cp /경로/blog-tool/saju-site/.nojekyll .
git add -A && git commit -m "AI 사주명리 사이트(랜딩+운영툴)" && git push
```

3. 저장소 **Settings → Pages → Source = main / 루트(/)** 로 배포
4. 고객용 주소: `https://<아이디>.github.io/saju-myeongri/`
   운영툴 주소: `https://<아이디>.github.io/saju-myeongri/admin.html`

## 2) 독립 도메인 연결 (예: `unmyeong.co.kr`)

1. 도메인 구입(가비아·후이즈·Cloudflare 등)
2. DNS 설정
   - 정점 도메인: A 레코드 4개 → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - www: CNAME → `<아이디>.github.io`
3. GitHub **Settings → Pages → Custom domain** 에 도메인 입력 → 저장 → **Enforce HTTPS** 체크

> `CNAME` 파일이 저장소에 자동 생성됩니다. 그대로 두세요.

---

## 운영자 도구(`admin.html`) 사용법

1. **⚙️ 설정**에서 Claude API 키 저장 (운영자 브라우저 localStorage에만 저장, 키 식별자 `saju_ak` — 블로그 도구와 분리)
   - 키 발급: https://console.anthropic.com
2. **📝 고객정보 입력 → 🀄 사주판 계산 → 🔮 프리미엄 분석 생성**
3. **📄 PDF / 🖼 이미지 / 📋 텍스트** 저장 → 고객에게 전달
- 분석 비용은 운영자 API 키로 청구(1건 수백 원~, 모델·분량에 따라 변동)
- `admin.html`은 키 없이는 분석이 생성되지 않으므로 URL이 노출돼도 무단 사용 불가

## 계산 정확도

- 사주팔자 4기둥: 24절기(태양황경)·일주(율리우스일) 천문 계산
- 양력/음력(윤달 포함) 자동 변환: 합삭(신월)·무중기 윤달 판정
- 오행 분포 / 십성(십신) / 대운(순행·역행·대운수) 산출
- 절기·합삭 경계 출생자는 시간대 보정에 따라 달라질 수 있어 전문 만세력 교차 확인 권장

## 면책

명리학 이론 기반 **상담·참고용 콘텐츠**이며 의료·법률·투자 판단을 대체하지 않습니다.
