<div align="center">

# 🔮 운명을 읽다 · AI 사주명리

**천문 계산 만세력 + Claude AI**가 함께 만드는 프리미엄 사주명리 분석 서비스

생년월일시 → 사주팔자·오행·십성·대운 정밀 산출 → AI 10파트 심층 리포트 → PDF·이메일 전달

</div>

---

## ✨ 한눈에 보기

- **백엔드 없는 정적 사이트** — GitHub Pages에 파일만 올리면 끝, 서버 비용 0원
- **고객용 랜딩 + 운영자 도구** 2화면 구성, 깔끔한 다크·골드 테마
- **고객 신청 폼** — 개인정보 동의, 오기입 발송불가 사전 공지, "결제 후 24시간 내 발송" 안내까지
- **천문 계산 만세력** — 24절기·합삭·윤달까지 직접 계산(외부 만세력 API 의존 없음)
- **결과 전달 2가지** — PDF 수동 첨부 / EmailJS 자동 이메일 발송
- **고객은 API 키 불필요** — 분석 비용은 운영자 키로만 청구

| 파일 | 용도 | 공개 |
|------|------|------|
| `index.html` | **고객용 랜딩 + 신청 폼** (소개·가격·FAQ·신청) | 공개 |
| `admin.html` | **운영자 전용 분석 도구** (만세력 계산 + AI 10파트 + 발송) | 운영자만 |
| `.nojekyll` | GitHub Pages가 파일을 그대로 서빙 | — |
| `README.md` | 본 문서 (배포·운영 가이드) | — |
| [`AUTOMATION.md`](AUTOMATION.md) | 결제 완료 → 자동 발송까지 **완전 자동화 설계** | — |

> 고객은 `index.html`만 봅니다. 운영자는 `…/admin.html`에서 Claude API 키를 한 번 저장한 뒤 분석을 생성합니다.

---

## 🚀 빠른 시작 (5분 배포)

```bash
# 1) 새 저장소 생성 후, 이 폴더의 파일만 루트에 올립니다
git clone https://github.com/<아이디>/saju-myeongri.git
cd saju-myeongri
cp /경로/blog-tool/saju-site/{index.html,admin.html,.nojekyll,README.md,AUTOMATION.md} .
git add -A && git commit -m "AI 사주명리 사이트" && git push
```

2. 저장소 **Settings → Pages → Source = `main` / 루트(`/`)**
3. 배포 완료
   - 고객용: `https://<아이디>.github.io/saju-myeongri/`
   - 운영툴: `https://<아이디>.github.io/saju-myeongri/admin.html`

---

## 🔄 사업 흐름 (반자동)

```
고객 신청 폼 입력 ─▶ 운영자 메일로 신청 도착 ─▶ 결제 확인
        │                                          │
        └─ "결제 후 24h 내 발송" 안내               ▼
                              admin.html: 사주판 계산 ─▶ AI 10파트 생성
                                                          │
                                       ┌──────────────────┴──────────────────┐
                                       ▼                                      ▼
                              📄 PDF 저장 후 첨부               📧 고객 이메일로 자동 발송
```

> 폼에는 *"이메일·연락처 오기입 시 발송 불가"* 사전 공지와 *"결제 완료 후 24시간 내 발송"* 마무리 메시지가 포함됩니다.
> 결제까지 **완전 자동화**(결제 웹훅 → 자동 생성·발송)하려면 → **[AUTOMATION.md](AUTOMATION.md)** 참고.

---

## ⚙️ 배포 전 설정

### A. 신청 폼 → 운영자 이메일 수신 (`index.html` 하단 `<script>`)
```js
const WEB3FORMS_KEY="YOUR_WEB3FORMS_ACCESS_KEY"; // ← 교체
const PAY_LINK="#";                              // ← 결제 링크로 교체
const FALLBACK_EMAIL="rlarudeh7778@gmail.com";   // 키 미설정 시 신청 받을 메일
```
- **Web3Forms**(무료·백엔드 불필요): [web3forms.com](https://web3forms.com) → 운영자 이메일 입력 → 발급된 **Access Key**를 붙여넣기. 신청이 들어오면 운영자 메일로 전체 내용 도착.
- **미설정이면** 폼이 자동으로 **`FALLBACK_EMAIL`로 메일 보내기(mailto)** 로 동작 (당장도 작동).
- **`PAY_LINK`**: 토스·카카오페이 등 결제 링크 → 성공 화면 「결제하기」 버튼에 연결.

### B. 가격·브랜드
- `<section id="price">`의 금액(19,000 / 39,000 / 49,000)은 예시 → 자유롭게 수정
- 상단 브랜드명 `운명을 읽다`, 히어로 카피 등 취향대로

### C. (선택) 결과 이메일 자동 발송 — `admin.html` ⚙️설정
PDF 수동 전달로 충분하면 건너뛰어도 됩니다. 자동 발송을 원할 때만:
1. [emailjs.com](https://emailjs.com) 무료 가입 → **Email Service** 연결(Gmail 등)
2. **Email Template** 생성 — 받는사람(To) `{{to_email}}`, 제목 `{{subject}}`, 본문(HTML) `{{message_html}}`
3. `admin.html` → ⚙️설정 → **📧 이메일 자동 발송**에 Public Key / Service ID / Template ID 입력·저장
4. 분석 완료 후 **「📧 고객 이메일로 발송」** 클릭 → 고객에게 바로 전송

---

## 🌐 독립 도메인 연결 (예: `unmyeong.co.kr`)

1. 도메인 구입(가비아·후이즈·Cloudflare 등)
2. DNS 설정
   - 정점 도메인: A 레코드 4개 → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www`: CNAME → `<아이디>.github.io`
3. GitHub **Settings → Pages → Custom domain** 입력 → 저장 → **Enforce HTTPS** 체크

> `CNAME` 파일이 저장소에 자동 생성됩니다. 그대로 두세요.

---

## 🛠 운영자 도구(`admin.html`) 사용법

1. **⚙️ 설정**에서 Claude API 키 저장 (운영자 브라우저 localStorage에만 저장, 키 식별자 `saju_ak`)
   - 키 발급: https://console.anthropic.com
2. **📝 고객정보 입력**(이메일 포함) → 🀄 **사주판 계산** → 🔮 **프리미엄 분석 생성**
3. **📄 PDF 저장 후 첨부** 또는 **📧 고객 이메일로 발송**(EmailJS 설정 시)
- 분석 비용은 운영자 API 키로 청구(1건 수백 원~, 모델·분량에 따라 변동)
- `admin.html`은 키 없이는 분석이 생성되지 않으므로 URL이 노출돼도 무단 사용 불가

---

## 🎯 계산 정확도

- 사주팔자 4기둥: 24절기(태양황경)·일주(율리우스일) 천문 계산
- 양력/음력(윤달 포함) 자동 변환: 합삭(신월)·무중기 윤달 판정
- 오행 분포 / 십성(십신) / 대운(순행·역행·대운수) 산출
- 절기·합삭 경계 출생자는 시간대 보정에 따라 달라질 수 있어 전문 만세력 교차 확인 권장

## ⚖️ 면책

명리학 이론 기반 **상담·참고용 콘텐츠**이며 의료·법률·투자 판단을 대체하지 않습니다.
