#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""워드프레스 완전 자동 발행 스크립트 (GitHub Actions cron).

흐름: 설정(autopost_config.json) → Claude로 글 생성(참고자료 각색·유사도 방지)
      → B스타일 모바일 HTML 조립 → 워드프레스 REST API로 자동 발행 → 상태 저장.

- IT 정보글 위주, N편마다 선불폰 글을 자동으로 끼워 넣음.
- 참고 자료(references)는 '사실 확인용'으로만 쓰고 문장·구조를 100% 새로 작성하도록 지시.
- 워드프레스 시크릿이 없으면 자동으로 DRY_RUN(발행하지 않고 로그/파일로만 미리보기).

필요 환경변수(시크릿):
  ANTHROPIC_API_KEY   (필수 - 글 생성)
  WP_URL              (예: https://example.com  → 없으면 DRY_RUN)
  WP_USER             (워드프레스 사용자명)
  WP_APP_PASSWORD     (워드프레스 '응용 프로그램 비밀번호')
선택:
  DRY_RUN=1           (강제로 발행 안 함)
  POSTS_PER_RUN=1     (이번 실행에서 발행할 글 수, 설정값보다 우선)
"""
import os
import re
import sys
import json
import html
import datetime
import traceback

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "autopost_config.json")
STATE_PATH = os.path.join(os.path.dirname(__file__), "autopost_state.json")
PREVIEW_DIR = os.path.join(os.path.dirname(__file__), "preview")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
WP_URL = os.environ.get("WP_URL", "").strip().rstrip("/")
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PW = os.environ.get("WP_APP_PASSWORD", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "").strip() == "1" or not (WP_URL and WP_USER and WP_APP_PW)


# ───────────────────────── 설정 / 상태 ─────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ───────────────────────── Claude 호출 ─────────────────────────
def claude(system, user, model, max_tokens=4000):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    return "".join(blk.get("text", "") for blk in data.get("content", []))


def parse_json(text):
    """모델 응답에서 첫 JSON 객체를 관대하게 추출."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("JSON 없음: " + text[:200])
    return json.loads(text[start:end + 1])


# ───────────────────────── 프롬프트 ─────────────────────────
COMMON_RULES = (
    "절대 준수:\n"
    "1. 제목은 키워드 단독 나열 금지 — 후킹 문구를 더해 클릭하고 싶게(35자 이내).\n"
    "2. 공백포함 2,000~2,500자.\n"
    "3. ## ** 등 마크다운 기호 금지.\n"
    "4. ★결론 먼저★ 도입부 첫 1~2문장에서 핵심 결론/답을 먼저 제시(결론 먼저 → 근거·방법 나중). "
    "그래야 독자가 이탈하지 않고 끝까지 읽음. 이어서 호기심을 자극하는 후킹 문장 1개.\n"
    "5. 소제목을 5개 이상 풍부하게 넣어 자주 끊을 것(스크롤·가독성↑). 그중 2~3개는 '~까요?' 질문형으로 → FAQ 자동 생성.\n"
    "6. 한 문단은 1~2문장으로 짧게, 모든 문장은 마침표/물음표로 종결(모바일 가독성).\n"
    "7. 각 소제목 다음엔 바로 핵심을 말하고, '그다음은?' 식으로 다음 소제목 내용을 궁금하게 연결.\n"
    "8. 강조 꿀팁은 한 줄 '[팁] ...', 주의는 '[주의] ...' 형식(각 1~2개, 선택).\n"
    "9. 구체적 수치 3개 이상. AI 티 나는 상투적 표현 금지.\n"
    "10. summary는 글 핵심(결론)을 25자 이내 3개로 — 맨 위 요약으로 노출됨.\n"
    'JSON만 출력(첫 글자 {): {"title":"...","summary":["..","..",".."],'
    '"content":"본문","hashtags":["t1","t2","t3","t4","t5","t6","t7","t8"]}'
)


def gen_it(topic, reference, model):
    system = ("너는 IT 정보 블로그 에디터다. 독자가 검색한 문제를 끝까지 해결해주는 "
              "신뢰감 있는 정보글을 쓴다. 광고 톤 없이 순수 정보 제공. JSON만 출력.")
    ref = ""
    if reference:
        ref = ("\n[참고 자료 - 사실 확인용으로만 사용]\n" + reference[:1500] +
               "\n※ 위 자료의 문장·구조·표현을 절대 그대로 쓰지 말 것. 어휘·흐름·예시를 100% 새로 "
               "작성해 표절/유사도 검사에 걸리지 않게 할 것. 사실 관계만 참고.\n")
    user = (
        "아래 주제로 IT 정보 블로그 글을 써라.\n"
        f"주제: {topic}\n"
        "구성: 증상/상황 공감(도입) → 원인 2~3가지 → 해결방법을 번호 소제목으로 단계별 → "
        "안 될 때 대안/전문가 안내로 마무리. 메뉴 경로·버튼명·단축키 등 구체적으로.\n"
        + ref + "\n" + COMMON_RULES
    )
    return parse_json(claude(system, user, model))


def gen_phone(keyword, brand, platform_url, model):
    system = ("너는 통신 정보 블로거다. 선불폰/알뜰폰 개통을 처음 하는 사람도 따라 하게 "
              "친절하고 신뢰감 있게 설명한다. 과장 광고 금지. JSON만 출력.")
    user = (
        f"아래 키워드로 선불폰 정보글을 써라.\n메인키워드: {keyword}\n"
        f'메인키워드 "{keyword}"는 제목에 포함하고 본문에서 정확히 3회만 사용.\n'
        "반드시 포함할 3섹션: (1) 유심 어떤 걸 사나 — KT망/LG망 구분, 편의점·온라인 구입처, "
        "가격(바로유심 8,800원선), 공기계·중고폰 사용 가능 (2) 요금제 — 망별 대표 요금제와 데이터·가격 "
        "(3) 개통 절차 — 순서대로(사이트 접속 → 유형선택 → 본인인증 → 유심정보 등록 → 요금제 선택 → "
        "번호 선택 → 신청, 5분/365일).\n"
        "개통 절차에서 '앤플랫폼 사이트 접속' 단계는 URL을 쓰지 말고 그 자리에 한 줄로 [앤플랫폼접속] 이라고만 적어라.\n"
        f"글 마무리에 '앤텔레콤 개통이나 선불폰 개통 문의는 {brand}'라고 자연스럽게 안내(미납·신용·외국인도 상담 가능).\n"
        "지역 키워드가 있으면 그 지역 정보(근처 편의점·동네 특징)를 1~2문장 녹여 차별화.\n\n"
        + COMMON_RULES
    )
    return parse_json(claude(system, user, model))


# ───────────────────────── HTML 조립 (B스타일·모바일) ─────────────────────────
def esc(s):
    return html.escape(str(s or ""), quote=True)


PALETTE = ["#1f9d59", "#2f7de1", "#e8841a", "#9d4edd", "#e23d6e", "#0ea5a5"]


def is_heading(line):
    t = line.strip()
    if not t or len(t) > 34:
        return False
    if re.match(r"^\s*\d{1,2}[.)]\s*", t):
        return True
    if re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", t):
        return True
    if t.endswith("?") or t.endswith("？"):
        return len(t) <= 30
    if len(t) <= 20 and not re.search(r"[.…!~,]$", t):
        return True
    return False


def clean_heading(t):
    return re.sub(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", re.sub(r"^\s*\d{1,2}[.)]\s*", "", t.strip())).strip()


def split_sentences(text):
    marked = re.sub(r"([.!?])\s+", r"\1@@S@@", text)
    return [s.strip() for s in marked.split("@@S@@") if s.strip()]


def paragraphize(text):
    sents = split_sentences(text)
    ps = "margin:0 0 20px"
    if len(sents) <= 1:
        return f'<p style="{ps}">{esc(text)}</p>'
    out, buf = "", []
    for s in sents:
        buf.append(s)
        if len(buf) >= 2:
            out += f'<p style="{ps}">{esc(" ".join(buf))}</p>'
            buf = []
    if buf:
        out += f'<p style="{ps}">{esc(" ".join(buf))}</p>'
    return out


def platform_btn(url):
    return ('<div style="text-align:center;margin:18px 0 24px">'
            f'<a href="{esc(url)}" target="_blank" rel="noopener" '
            'style="display:inline-block;background:#2f7de1;color:#fff;padding:14px 28px;'
            'border-radius:12px;font-weight:800;font-size:15px;text-decoration:none">'
            '🖥️ 앤플랫폼 개통 홈페이지 접속 →</a></div>')


def adsense_block(cfg):
    client = cfg.get("adsense_client", "")
    slot = cfg.get("adsense_slot", "")
    if client and slot:
        return ('<div style="text-align:center;margin:30px 0">'
                f'<ins class="adsbygoogle" style="display:block;text-align:center" '
                f'data-ad-layout="in-article" data-ad-format="fluid" '
                f'data-ad-client="{esc(client)}" data-ad-slot="{esc(slot)}"></ins>'
                '<script>(adsbygoogle = window.adsbygoogle || []).push({});</script></div>')
    return ('<div style="text-align:center;margin:30px 0;padding:22px;background:#fafafa;'
            'border:1px dashed #d0d0d0;border-radius:10px;color:#999;font-size:13px">'
            '＜ 구글 애드센스 광고 자리 ＞</div>')


def contact_block(cfg):
    brand = cfg.get("brand", "메이플통신")
    kakao = cfg.get("kakao", "#")
    channel = cfg.get("channel", "")
    tel = re.sub(r"[^0-9+]", "", cfg.get("tel", "")) or "01000000000"
    btn = ("display:inline-block;padding:15px 26px;border-radius:30px;font-weight:800;"
           "font-size:15px;text-decoration:none;margin:5px")
    h = ('<div style="text-align:center;margin:38px 0 0;padding:30px 18px;'
         'background:linear-gradient(135deg,#1f9d59,#157a44);border-radius:18px">'
         f'<div style="font-size:19px;font-weight:800;color:#fff;margin-bottom:6px">📞 앤텔레콤·선불폰 개통 문의는 {esc(brand)}</div>'
         '<div style="font-size:13px;color:#e7f6ee;margin-bottom:16px">약정·미납 상관없이 상담 가능합니다.</div>'
         f'<a href="{esc(kakao)}" target="_blank" rel="noopener" style="{btn};background:#FEE500;color:#191600">💬 오픈채팅</a>')
    if channel:
        h += f'<a href="{esc(channel)}" target="_blank" rel="noopener" style="{btn};background:#FEE500;color:#191600">📢 카톡채널</a>'
    h += f'<a href="tel:{esc(tel)}" style="{btn};background:#fff;color:#1f9d59">📱 전화</a></div>'
    return h


def org_ld(cfg):
    brand = cfg.get("brand", "메이플통신")
    o = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": brand,
         "description": f"{brand}은 앤텔레콤 선불폰·알뜰폰 개통을 도와드리는 통신 서비스입니다.",
         "areaServed": "KR", "knowsAbout": ["앤텔레콤 개통", "선불폰 개통", "알뜰폰 개통"]}
    if cfg.get("tel"):
        o["telephone"] = cfg["tel"]
    sameas = [x for x in [cfg.get("kakao"), cfg.get("channel")] if x]
    if sameas:
        o["sameAs"] = sameas
    return o


def build_html(post, kind, cfg):
    body = post.get("content", "")
    summary = post.get("summary", []) or []
    platform_url = cfg.get("platform_url", "https://www.n-telecom.co.kr/junda")

    blocks = []
    for ln in body.split("\n"):
        t = ln.strip()
        if not t:
            continue
        if "[앤플랫폼접속]" in t or "n-telecom.co.kr" in t:
            blocks.append(("platbtn", ""))
        elif re.match(r"^\[?\s*팁\s*\]", t):
            blocks.append(("tip", re.sub(r"^\[?\s*팁\s*\]\s*", "", t)))
        elif re.match(r"^\[?\s*주의\s*\]", t):
            blocks.append(("caution", re.sub(r"^\[?\s*주의\s*\]\s*", "", t)))
        elif is_heading(t):
            blocks.append(("h", clean_heading(t)))
        else:
            blocks.append(("p", t))

    heading_idx = [i for i, b in enumerate(blocks) if b[0] == "h"]
    first_h = heading_idx[0] if heading_idx else len(blocks)

    # FAQ (질문형 소제목 + 다음 문단)
    faqs = []
    for i, b in enumerate(blocks):
        if b[0] == "h" and (b[1].endswith("?") or b[1].endswith("？")):
            ans = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "p" else ""
            if ans:
                faqs.append((b[1], ans))

    out = ['<div style="max-width:760px;margin:0 auto;font-size:17px;line-height:1.85;'
           'color:#2b2b2b;word-break:keep-all;overflow-wrap:break-word">']

    lead = [esc(blocks[i][1]) for i in range(first_h) if blocks[i][0] == "p"]
    if lead:
        out.append('<div style="background:linear-gradient(135deg,#eafaf2,#f3f9ff);'
                   'border:1px solid #d8eee2;border-radius:14px;padding:20px 22px;margin:0 0 24px">'
                   '<p style="margin:0">' + "<br><br>".join(lead) + "</p></div>")
    if summary:
        out.append('<div style="background:#fffdf5;border:1px solid #f0e0b5;border-radius:12px;'
                   'padding:18px 20px;margin:0 0 28px">'
                   f'<div style="font-weight:800;color:#b8860b;margin-bottom:10px;font-size:15px">📌 {len(summary)}줄 요약</div>'
                   '<div style="line-height:1.95;color:#444">' +
                   "<br>".join("✅ " + esc(x) for x in summary) + "</div></div>")

    # 본문 중간 애드센스 위치: 2번째 소제목 앞 + 중간 소제목 앞
    ad_before = set()
    if len(heading_idx) >= 2:
        ad_before.add(heading_idx[1])
    if len(heading_idx) >= 4:
        ad_before.add(heading_idx[len(heading_idx) // 2])

    hi = 0
    for i in range(first_h, len(blocks)):
        typ, txt = blocks[i]
        if i in ad_before:
            out.append(adsense_block(cfg))
        if typ == "h":
            hi += 1
            c = PALETTE[(hi - 1) % len(PALETTE)]
            out.append(f'<h2 style="font-size:21px;font-weight:800;color:#111;margin:36px 0 14px;'
                       'display:flex;align-items:center;gap:10px">'
                       f'<span style="background:{c};color:#fff;min-width:30px;height:30px;border-radius:9px;'
                       f'display:inline-flex;align-items:center;justify-content:center;font-size:15px">{hi}</span>{esc(txt)}</h2>')
        elif typ == "tip":
            out.append('<div style="background:#f0f9f4;border-left:4px solid #1f9d59;border-radius:8px;'
                       f'padding:12px 16px;margin:0 0 22px"><b>💡 꿀팁</b> &nbsp;{esc(txt)}</div>')
        elif typ == "caution":
            out.append('<div style="background:#fdf2f4;border-left:4px solid #e23d6e;border-radius:8px;'
                       f'padding:12px 16px;margin:0 0 22px"><b>⚠️ 주의</b> &nbsp;{esc(txt)}</div>')
        elif typ == "platbtn":
            out.append(platform_btn(platform_url))
        else:
            out.append(paragraphize(txt))

    if faqs:
        out.append('<hr style="border:none;border-top:2px dashed #e5e5e5;margin:32px 0">'
                   '<div style="font-size:19px;font-weight:800;color:#111;margin:0 0 16px">❓ 자주 묻는 질문</div>')
        for q, a in faqs:
            out.append('<div style="margin:0 0 10px;padding:0 0 12px;border-bottom:1px solid #eee">'
                       f'<div style="font-weight:700;color:#2f7de1;margin-bottom:5px">Q. {esc(q)}</div>'
                       f'<div style="color:#444;line-height:1.85">{esc(a)}</div></div>')

    if kind == "phone":
        out.append(contact_block(cfg))
    out.append("</div>")

    # 구조화데이터 (워드프레스는 본문 script 유지)
    if faqs:
        ld = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q,
                              "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}
        out.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>")
    if kind == "phone":
        out.append('<script type="application/ld+json">' + json.dumps(org_ld(cfg), ensure_ascii=False) + "</script>")

    return "\n".join(out)


# ───────────────────────── 워드프레스 발행 ─────────────────────────
def publish_wp(title, content_html, excerpt, status):
    url = WP_URL + "/wp-json/wp/v2/posts"
    payload = {"title": title, "content": content_html, "status": status}
    if excerpt:
        payload["excerpt"] = excerpt
    r = requests.post(url, json=payload, auth=(WP_USER, WP_APP_PW), timeout=90)
    r.raise_for_status()
    return r.json()


# ───────────────────────── 메인 ─────────────────────────
def main():
    if not ANTHROPIC_KEY:
        print("⏭ ANTHROPIC_API_KEY 미설정 — 자동 발행 건너뜀(설정 전이라 정상). "
              "scripts/AUTOPOST_README.md 참고해 시크릿 등록 후 활성화됩니다.")
        return

    cfg = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"it_idx": 0, "phone_idx": 0, "ref_idx": 0, "counter": 0, "log": []})
    state.setdefault("ref_idx", 0)
    contact = cfg.get("contact", {})
    model = cfg.get("model", "claude-sonnet-4-6")
    it_topics = cfg.get("it_topics", [])
    phone_kws = cfg.get("phone_keywords", [])
    references = cfg.get("references", [])
    phone_every = max(0, int(cfg.get("phone_every", 5)))
    posts = int(os.environ.get("POSTS_PER_RUN", cfg.get("posts_per_run", 1)))
    status = cfg.get("wp_status", "publish")

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    print(f"▶ 시작 | DRY_RUN={DRY_RUN} | 모델={model} | 이번 발행 {posts}편 | "
          f"IT {len(it_topics)}주제 / 선불폰 {len(phone_kws)}키워드 / 참고 {len(references)}건")

    done = 0
    for _ in range(posts):
        state["counter"] += 1
        # 선불폰 삽입 판단: phone_every 편마다 1편(0이면 선불폰 안 씀)
        is_phone = phone_every > 0 and phone_kws and (state["counter"] % phone_every == 0)
        try:
            if is_phone:
                kw = phone_kws[state["phone_idx"] % len(phone_kws)]
                state["phone_idx"] += 1
                post = gen_phone(kw, contact.get("brand", "메이플통신"),
                                 cfg.get("platform_url", "https://www.n-telecom.co.kr/junda"), model)
                kind = "phone"
                label = f"[선불폰] {kw}"
            else:
                kind = "it"
                # 사용자가 준 참고자료가 남아있으면 그걸 우선 각색(1자료=1글), 소진되면 주제 뱅크로
                if references and state["ref_idx"] < len(references):
                    rf = references[state["ref_idx"]]
                    state["ref_idx"] += 1
                    topic = (rf.get("title") or "IT 정보").strip()
                    post = gen_it(topic, rf.get("text", ""), model)
                    label = f"[IT/각색] {topic}"
                elif it_topics:
                    topic = it_topics[state["it_idx"] % len(it_topics)]
                    state["it_idx"] += 1
                    post = gen_it(topic, "", model)
                    label = f"[IT] {topic}"
                else:
                    print("⚠ IT 주제/참고자료가 없습니다. autopost_config.json을 채우세요.")
                    break

            title = post.get("title", "").strip()
            excerpt = " ".join(post.get("summary", []))[:150]
            content_html = build_html(post, kind, {**contact, "platform_url": cfg.get("platform_url"),
                                                   "adsense_client": cfg.get("adsense_client", ""),
                                                   "adsense_slot": cfg.get("adsense_slot", "")})

            if DRY_RUN:
                fn = os.path.join(PREVIEW_DIR, f"{datetime.date.today()}_{state['counter']}.html")
                with open(fn, "w", encoding="utf-8") as f:
                    f.write(f"<!doctype html><meta charset=utf-8><title>{esc(title)}</title>"
                            f"<body style='background:#eee;padding:20px'><div style='max-width:820px;margin:auto;"
                            f"background:#fff;padding:30px;border-radius:12px'><h1>{esc(title)}</h1>{content_html}</div>")
                print(f"  ✓ (DRY_RUN) 생성: {label} → {title}  [{fn}]")
            else:
                res = publish_wp(title, content_html, excerpt, status)
                print(f"  ✓ 발행: {label} → {title}  (id={res.get('id')}, {res.get('link')})")

            state["log"].append({"t": datetime.datetime.utcnow().isoformat(), "kind": kind,
                                 "label": label, "title": title})
            done += 1
        except Exception as e:
            print(f"  ✗ 실패: {label if 'label' in dir() else '?'} — {e}")
            traceback.print_exc()

    state["log"] = state["log"][-200:]
    save_json(STATE_PATH, state)
    print(f"■ 완료: {done}편 처리. 상태 저장됨.")


if __name__ == "__main__":
    main()
