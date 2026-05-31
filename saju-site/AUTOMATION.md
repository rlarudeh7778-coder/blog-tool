# 🤖 결제 → 발송 완전 자동화 설계

현재 사이트는 **반자동**입니다(고객 신청·결제 → 운영자가 `admin.html`에서 생성·발송).
이 문서는 **결제가 완료되면 사람 손 없이 사주 리포트가 자동 생성·발송**되도록
확장하는 설계를 설명합니다.

---

## 1. 왜 GitHub Pages만으론 불가능한가

GitHub Pages는 **정적 호스팅**입니다. HTML/CSS/JS 파일을 그대로 보여줄 뿐,
**서버에서 코드를 실행할 수 없습니다.** 그런데 완전 자동화에는 서버 실행이 필요합니다:

| 작업 | 왜 서버가 필요한가 |
|------|--------------------|
| 결제 **웹훅 수신** | 결제사(토스/스트라이프)가 "결제 완료"를 **서버 URL로 POST** 합니다. 정적 페이지는 POST를 받을 수 없음 |
| **Claude API 호출** | API 키를 클라이언트에 두면 누구나 훔쳐 씁니다. 키는 **서버에만** 둬야 함 |
| **이메일 발송** | 결제 시점에 브라우저가 열려 있지 않으므로, 서버가 대신 보내야 함 |
| 웹훅 **서명 검증** | 가짜 결제 알림을 막으려면 시크릿으로 서명 검증 — 서버에서만 안전 |

→ **결론:** 정적 사이트(랜딩)는 그대로 두고, **서버리스 함수(Function) 하나**만 추가하면 됩니다.
서버를 24시간 켜둘 필요 없이, 요청이 올 때만 실행되고 과금되는 방식입니다.

---

## 2. 목표 아키텍처

```
 ┌─────────────┐   결제    ┌──────────────┐  웹훅(POST)   ┌─────────────────────────┐
 │  고객 (랜딩) │ ───────▶ │  결제사       │ ───────────▶ │  서버리스 함수            │
 │ index.html  │          │ (토스/스트라이프)            │  /api/payment-webhook    │
 └─────────────┘          └──────────────┘              │                          │
        ▲  신청 폼(주문 메타: 이름/생년월일시/이메일)      │  ① 서명 검증              │
        │                                               │  ② 주문 정보 조회         │
        │                                               │  ③ Claude API로 10파트 생성│
        │                                               │  ④ 이메일(PDF/HTML) 발송  │
        └───────────── 확인 메일 자동 수신 ◀────────────│  ⑤ 주문 상태=완료 기록    │
                                                         └─────────────────────────┘
                                                              (키·시크릿은 서버 환경변수)
```

핵심 원칙
- **Claude API 키, 이메일 키, 웹훅 시크릿**은 전부 **서버 환경변수**에 둔다(클라이언트 노출 0).
- 결제와 주문 데이터를 **주문 ID로 연결**한다(웹훅은 금액·주문ID만 주므로, 생년월일시는 우리가 보관).

---

## 3. 서버리스 플랫폼 선택지 (무료 티어 충분)

| 플랫폼 | 함수 | 데이터 저장 | 특징 |
|--------|------|-------------|------|
| **Cloudflare Workers** | Workers | KV / D1 | 무료 10만 req/일, 가장 가볍고 빠름 (추천) |
| **Vercel** | Serverless/Edge Functions | Vercel KV / 외부 DB | Next.js 친화, 배포 간단 |
| **Netlify** | Functions | 외부 DB | Pages와 통합 쉬움 |
| **Supabase** | Edge Functions | Postgres 내장 | DB·인증·저장 한 번에 |

> 정적 랜딩은 GitHub Pages에 그대로 두고, **함수만** 위 중 하나에 올려도 됩니다(도메인 분리 OK).
> 또는 사이트째 Cloudflare Pages/Vercel로 옮기면 정적+함수를 한 곳에서 관리할 수 있습니다.

---

## 4. 결제 연동 방식 2가지

### (A) 결제 링크 + 웹훅 — 가장 간단
1. 토스페이먼츠/스트라이프에서 **상품별 결제 링크(Payment Link)** 생성
2. 랜딩 신청 폼 제출 → 우리 함수 `/api/create-order`가 **주문을 저장**하고 결제 링크로 보냄
   (주문ID를 결제 `metadata`/`orderId`에 실어 보냄)
3. 고객 결제 완료 → 결제사가 `/api/payment-webhook`으로 POST
4. 함수가 주문ID로 사주 메타를 찾아 **생성·발송** 후 상태를 `완료`로 갱신

### (B) 결제창 직접 연동(SDK)
- 토스페이먼츠 JS SDK로 랜딩에서 결제창을 띄우고, 승인(confirm) 콜백에서 함수 호출.
- UX가 매끄럽지만 구현량이 더 많음. 처음엔 (A) 권장.

---

## 5. 웹훅 함수 의사코드 (Cloudflare Workers 예시)

> 실제 키/시크릿은 `wrangler secret`(환경변수)로 주입. 아래는 골격 예시입니다.

```js
export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("ok");      // 헬스체크
    const raw = await req.text();

    // ① 웹훅 서명 검증 (위조 결제 차단) — 결제사 시크릿으로 HMAC 비교
    if (!verifySignature(raw, req.headers, env.WEBHOOK_SECRET))
      return new Response("bad signature", { status: 401 });

    const event = JSON.parse(raw);
    if (event.type !== "payment.completed") return new Response("ignored");

    // ② 주문 정보 조회 (신청 폼에서 미리 저장한 사주 메타)
    const orderId = event.data.orderId;
    const order = await env.ORDERS.get(orderId, "json");        // KV에서 조회
    if (!order || order.status === "sent") return new Response("dup"); // 멱등 처리

    // ③ 사주판 계산 + Claude로 10파트 생성
    const saju = computeSaju(order);                            // admin.html 엔진 이식
    const report = await generateReport(saju, env.ANTHROPIC_API_KEY);

    // ④ 이메일 발송 (Resend / SendGrid 등 — PDF 첨부 가능)
    await sendEmail(env.RESEND_API_KEY, {
      to: order.email,
      subject: `${order.name} 님 사주명리 리포트`,
      html: report.html,
      attachments: [{ filename: "saju.pdf", content: report.pdfBase64 }],
    });

    // ⑤ 상태 갱신(재발송 방지)
    order.status = "sent";
    await env.ORDERS.put(orderId, JSON.stringify(order));
    return new Response("done");
  },
};
```

필요한 환경변수(시크릿)
```
ANTHROPIC_API_KEY   # Claude API 키 (서버에만!)
WEBHOOK_SECRET      # 결제사 웹훅 서명 검증용
RESEND_API_KEY      # 이메일 발송 키 (Resend 추천: PDF 첨부 지원)
```

---

## 6. 만세력 엔진·프롬프트 재사용

`admin.html` 안의 **만세력 계산 엔진**(`computeSaju`/`lunarToSolar`/`analyzeSaju`)과
**10파트 프롬프트**(`PARTS`, `sysPrompt`)는 순수 JS라 **서버 함수로 그대로 이식 가능**합니다.
→ 별도 모듈(`engine.js`)로 분리해 `admin.html`과 서버 함수가 **같은 코드를 공유**하면
   클라이언트/서버 결과가 100% 일치합니다.

---

## 7. PDF 첨부 자동 생성

서버에서 PDF를 만들려면:
- **Resend + React Email / HTML→PDF** (예: `puppeteer`는 무겁고, 경량은 `@react-pdf/renderer`)
- 또는 Cloudflare **Browser Rendering**(베타)로 HTML을 PDF로 렌더
- 간단히 가려면 **HTML 본문 메일**로 보내고 PDF는 생략해도 됨(현재 EmailJS 방식과 동일)

---

## 8. 단계적 도입 로드맵

| 단계 | 상태 | 작업 |
|------|------|------|
| **0. 반자동** | ✅ 현재 | 신청 폼 + 운영자 수동 생성/발송 |
| **1. 주문 저장** | 다음 | 폼 제출을 함수로 받아 주문ID 발급·저장(KV) |
| **2. 결제 웹훅** | | 결제사 웹훅 → 서명 검증 → 상태 추적 |
| **3. 자동 생성** | | 엔진·프롬프트 서버 이식 → Claude 호출 |
| **4. 자동 발송** | | 이메일(PDF/HTML) 자동 발송 + 멱등 처리 |
| **5. 운영 대시보드** | 선택 | 주문/매출 조회, 재발송 버튼 |

> **권장:** 1·2단계만 먼저 붙여도 "결제 자동 확인 + 운영자 알림"이 되어 실수가 크게 줍니다.
> 3·4단계(완전 무인 발송)는 품질 검수를 한 번 거치고 싶다면 의도적으로 반자동으로 남겨두는 것도 전략입니다
> (사주는 민감 콘텐츠라 자동 발송 전 사람이 한번 보는 편이 클레임 방지에 유리).

---

## 9. 비용·보안 메모

- **비용**: 서버리스 함수·KV 무료 티어로 소규모는 사실상 0원. 변동비는 Claude API + 이메일 발송비.
- **보안**: API 키·시크릿은 **반드시 서버 환경변수**. 클라이언트(`admin.html`)에 키를 두는 현재 방식은
  *운영자 본인만 쓰는 전제*에서 안전하며, 공개 자동화로 갈수록 **서버로 키를 옮기는 것이 필수**입니다.
- **개인정보**: 생년월일시·이메일은 발송 완료 후 파기 정책 유지(랜딩 동의 문구와 일치시킬 것).
