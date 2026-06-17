#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""일회용: 애드센스 승인용 필수 페이지(소개·문의·개인정보처리방침)를 워드프레스에 생성.

- /wp-json/wp/v2/pages 로 '페이지'(글이 아님)를 publish 상태로 생성.
- 멱등(idempotent): 같은 slug 페이지가 이미 있으면 건너뜀(덮어쓰지 않음).
- <script> 등 보안 플러그인(NinjaFirewall)이 막는 요소는 쓰지 않음(순수 텍스트/링크/목록).

환경변수:
  WP_URL, WP_USER, WP_APP_PASSWORD (필수)
  DRY_RUN=1  (실제 생성 없이 무엇을 만들지 미리보기만)
"""
import os
import sys

import requests

WP_URL = os.environ.get("WP_URL", "").strip().rstrip("/")
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PW = os.environ.get("WP_APP_PASSWORD", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "").strip() == "1"

WP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

EMAIL = "rlarudeh7778@gmail.com"
TODAY = "2026년 6월 17일"

ABOUT_HTML = (
    "<p>메이플통신은 컴퓨터·스마트폰·인터넷을 쓰면서 누구나 한 번쯤 막히는 문제들을, "
    "초보자도 그대로 따라 할 수 있게 풀어주는 IT 생활정보 블로그입니다.</p>"
    "<p>윈도우 오류, 노트북 발열, 와이파이 끊김, 프린터 오프라인, 엑셀·한글 사용법처럼 "
    "검색해도 막상 따라 하기 어려운 주제를, 실제 화면 메뉴와 버튼 위치까지 짚어가며 정리합니다.</p>"
    "<p>운영자는 통신·IT 분야에서 직접 기기를 다루고 고객 문의를 처리해온 경험을 바탕으로, "
    "인터넷에 흔한 원론적인 답변 대신 ‘실제로 해결되는 방법’을 우선합니다.</p>"
    "<p>이 블로그의 모든 글은 독자가 글 하나로 문제를 끝낼 수 있도록 작성하는 것을 목표로 합니다. "
    "도움이 필요한 내용이나 궁금한 점은 문의 페이지를 통해 알려주세요.</p>"
)

CONTACT_HTML = (
    "<p>메이플통신에 궁금한 점이나 다루었으면 하는 주제, 글 내용 관련 문의가 있으시면 "
    "아래로 연락 주세요.</p>"
    f'<p>이메일: <a href="mailto:{EMAIL}">{EMAIL}</a></p>'
    "<p>콘텐츠 제휴, 오타·오류 정정 요청, 주제 제안 모두 환영합니다. "
    "보내주신 문의는 확인 후 순차적으로 답변드립니다.</p>"
)

PRIVACY_HTML = (
    "<p>메이플통신(이하 ‘사이트’)은 이용자의 개인정보를 중요하게 생각하며, 관련 법령을 준수합니다.</p>"
    "<h2>1. 수집하는 정보</h2>"
    "<p>본 사이트는 회원가입 기능이 없으며 이름·연락처 등 개인정보를 직접 수집하지 않습니다. "
    "다만 방문 통계와 광고 제공을 위해 쿠키(cookie)와 접속 로그가 자동으로 수집될 수 있습니다.</p>"
    "<h2>2. 쿠키와 광고</h2>"
    "<p>본 사이트는 제3자 광고 게재를 위해 구글 애드센스(Google AdSense)를 사용합니다. "
    "구글을 포함한 제3자 광고 사업자는 쿠키를 사용하여 이용자의 관심사에 기반한 광고를 제공할 수 있습니다.</p>"
    "<ul>"
    "<li>구글은 광고 쿠키를 사용해 이용자가 본 사이트나 다른 사이트를 방문한 기록을 바탕으로 광고를 게재합니다.</li>"
    '<li>이용자는 <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener">구글 광고 설정</a>'
    "에서 맞춤 광고를 끌 수 있습니다.</li>"
    '<li>또는 <a href="https://www.aboutads.info" target="_blank" rel="noopener">www.aboutads.info</a>'
    "에서 제3자 업체의 맞춤 광고 쿠키 사용을 거부할 수 있습니다.</li>"
    "<li>브라우저 설정에서 쿠키를 직접 차단할 수도 있습니다.</li>"
    "</ul>"
    "<h2>3. 통계 도구</h2>"
    "<p>본 사이트는 방문 분석을 위해 구글 애널리틱스 등 분석 도구를 사용할 수 있으며, "
    "이때 수집되는 정보는 통계 목적으로만 활용됩니다.</p>"
    "<h2>4. 개인정보 보호</h2>"
    "<p>본 사이트는 수집된 접속 정보를 광고·통계 목적 외에 이용하지 않으며, "
    "제3자에게 판매하거나 임의로 제공하지 않습니다.</p>"
    "<h2>5. 문의</h2>"
    f'<p>개인정보 관련 문의는 <a href="mailto:{EMAIL}">{EMAIL}</a> 으로 연락 주시기 바랍니다.</p>'
    f"<p>본 방침은 {TODAY}부터 적용됩니다.</p>"
)

PAGES = [
    {"slug": "about", "title": "메이플통신 소개", "content": ABOUT_HTML},
    {"slug": "contact", "title": "문의하기", "content": CONTACT_HTML},
    {"slug": "privacy-policy", "title": "개인정보처리방침", "content": PRIVACY_HTML},
]


def page_exists(slug):
    url = WP_URL + "/wp-json/wp/v2/pages"
    try:
        r = requests.get(url, params={"slug": slug, "status": "publish,draft,pending,private"},
                         headers={"User-Agent": WP_UA}, auth=(WP_USER, WP_APP_PW), timeout=60)
        if r.status_code == 400:
            r = requests.get(url, params={"slug": slug}, headers={"User-Agent": WP_UA},
                             auth=(WP_USER, WP_APP_PW), timeout=60)
        r.raise_for_status()
        arr = r.json()
        if arr:
            return arr[0].get("id"), arr[0].get("link")
    except Exception as e:
        print(f"  (존재 확인 실패 {slug}: {e})")
    return None, None


def create_page(p):
    url = WP_URL + "/wp-json/wp/v2/pages"
    payload = {"title": p["title"], "content": p["content"], "slug": p["slug"], "status": "publish"}
    r = requests.post(url, json=payload, headers={"User-Agent": WP_UA},
                      auth=(WP_USER, WP_APP_PW), timeout=90)
    r.raise_for_status()
    j = r.json()
    return j.get("id"), j.get("link")


def main():
    if not (WP_URL and WP_USER and WP_APP_PW):
        print("⏭ 워드프레스 시크릿(WP_URL/WP_USER/WP_APP_PASSWORD) 미설정 — 종료.")
        sys.exit(0)

    print(f"▶ 필수 페이지 {len(PAGES)}개 생성 시작 | DRY_RUN={DRY_RUN}")
    created, skipped = 0, 0
    for p in PAGES:
        pid, link = page_exists(p["slug"])
        if pid:
            print(f"  · 이미 있음(건너뜀) [{p['title']}] id={pid} {link or ''}")
            skipped += 1
            continue
        if DRY_RUN:
            print(f"  · (DRY_RUN) 생성 예정 [{p['title']}] slug={p['slug']}")
            continue
        try:
            nid, nlink = create_page(p)
            print(f"  ✓ 생성 [{p['title']}] id={nid} {nlink or ''}")
            created += 1
        except Exception as e:
            print(f"  ✗ 생성 실패 [{p['title']}]: {e}")
    print(f"■ 완료: {'(미리보기) ' if DRY_RUN else ''}생성 {created}개, 건너뜀 {skipped}개.")
    print("※ 워드프레스 관리자 → 외모 → 메뉴 에서 이 페이지들을 하단(푸터) 메뉴에 추가하면 애드센스 검토에 유리합니다.")


if __name__ == "__main__":
    main()
