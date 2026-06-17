#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""일회용: '사이트 정보' 메뉴를 만들고 소개·문의·개인정보처리방침 페이지를 넣은 뒤
테마의 푸터(하단) 메뉴 위치에 연결한다(애드센스 검토 대비).

흐름:
  1) /wp/v2/menus 에 같은 이름 메뉴가 있으면 건너뜀(멱등)
  2) /wp/v2/menu-locations 로 테마가 제공하는 메뉴 위치 조회 → 푸터/하단류 우선 선택
  3) 메뉴 생성(가능하면 location 지정) → 3개 페이지를 menu-items로 추가
  4) location 지정이 안 되면 메뉴만 만들고 안내(관리자에서 한 번 클릭으로 위치 지정)

환경변수: WP_URL, WP_USER, WP_APP_PASSWORD (필수), DRY_RUN=1(미리보기)
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
AUTH = (WP_USER, WP_APP_PW)

MENU_NAME = "사이트 정보"
PAGE_SLUGS = ["about", "contact", "privacy-policy"]
# 푸터/하단으로 볼 만한 위치 키워드(슬러그·이름 모두 검사)
FOOTER_HINTS = ["footer", "푸터", "하단", "bottom", "secondary", "sub"]


def jget(path, **params):
    r = requests.get(WP_URL + path, params=params or None, headers={"User-Agent": WP_UA},
                     auth=AUTH, timeout=60)
    r.raise_for_status()
    return r.json()


def jpost(path, payload):
    r = requests.post(WP_URL + path, json=payload, headers={"User-Agent": WP_UA},
                      auth=AUTH, timeout=90)
    r.raise_for_status()
    return r.json()


def find_menu(name):
    try:
        for m in jget("/wp-json/wp/v2/menus", search=name, per_page=50):
            if (m.get("name") or "").strip() == name:
                return m.get("id")
    except Exception as e:
        print(f"  (메뉴 조회 실패: {e})")
    return None


def pick_footer_location():
    """테마 메뉴 위치 중 푸터류를 우선 선택. 없으면 첫 위치, 그것도 없으면 None."""
    try:
        locs = jget("/wp-json/wp/v2/menu-locations")  # dict: slug -> {name, ...}
    except Exception as e:
        print(f"  (메뉴 위치 조회 실패 — 위치 지정 생략: {e})")
        return None, {}
    if not isinstance(locs, dict) or not locs:
        return None, {}
    for slug, info in locs.items():
        name = (info.get("name") if isinstance(info, dict) else "") or ""
        hay = (slug + " " + name).lower()
        if any(h in hay for h in FOOTER_HINTS):
            return slug, locs
    # 푸터류가 없으면 첫 번째 위치라도 사용
    first = next(iter(locs.keys()))
    return first, locs


def page_id(slug):
    try:
        arr = jget("/wp-json/wp/v2/pages", slug=slug)
        if arr:
            return arr[0].get("id"), (arr[0].get("title", {}) or {}).get("rendered", slug)
    except Exception as e:
        print(f"  (페이지 조회 실패 {slug}: {e})")
    return None, slug


def main():
    if not (WP_URL and WP_USER and WP_APP_PW):
        print("⏭ 워드프레스 시크릿 미설정 — 종료.")
        sys.exit(0)

    print(f"▶ 메뉴 구성 시작 | DRY_RUN={DRY_RUN}")

    if find_menu(MENU_NAME):
        print(f"  · 메뉴 '{MENU_NAME}' 이미 있음 — 건너뜀(중복 방지).")
        print("■ 완료(변경 없음).")
        return

    loc, locs = pick_footer_location()
    if locs:
        print(f"  · 사용 가능한 메뉴 위치: {list(locs.keys())}")
    print(f"  · 선택된 위치: {loc or '(없음 — 위치 미지정으로 생성)'}")

    # 페이지 id 수집
    items = []
    for slug in PAGE_SLUGS:
        pid, title = page_id(slug)
        if pid:
            items.append((pid, title, slug))
        else:
            print(f"  · 페이지 없음(건너뜀): {slug}")

    if DRY_RUN:
        print(f"  · (DRY_RUN) 메뉴 '{MENU_NAME}' 생성 + 항목 {len(items)}개 + 위치 {loc} 예정")
        print("■ 완료(미리보기).")
        return

    # 메뉴 생성 (가능하면 location 동시 지정)
    payload = {"name": MENU_NAME}
    if loc:
        payload["locations"] = [loc]
    menu = jpost("/wp-json/wp/v2/menus", payload)
    menu_id = menu.get("id")
    assigned = menu.get("locations") or []
    print(f"  ✓ 메뉴 생성 id={menu_id}, 위치={assigned or '미지정'}")

    # 항목 추가
    added = 0
    for pid, title, slug in items:
        try:
            jpost("/wp-json/wp/v2/menu-items", {
                "title": title, "menus": menu_id, "status": "publish",
                "type": "post_type", "object": "page", "object_id": pid,
            })
            print(f"    ✓ 항목 추가: {title} (page id={pid})")
            added += 1
        except Exception as e:
            print(f"    ✗ 항목 추가 실패 {slug}: {e}")

    # 위치가 생성 시 안 먹었으면 업데이트로 한 번 더 시도
    if loc and not assigned:
        try:
            up = jpost(f"/wp-json/wp/v2/menus/{menu_id}", {"locations": [loc]})
            print(f"  ✓ 위치 재지정: {up.get('locations')}")
            assigned = up.get("locations") or []
        except Exception as e:
            print(f"  · 위치 자동지정 실패(관리자에서 수동 지정 필요): {e}")

    print(f"■ 완료: 메뉴 1개, 항목 {added}개.")
    if not assigned:
        print("※ 위치 자동지정이 안 됐어요. 워드프레스 관리자 → 외모 → 메뉴 → "
              f"'{MENU_NAME}' 메뉴의 '메뉴 설정'에서 푸터 위치 체크 후 저장하면 됩니다.")


if __name__ == "__main__":
    main()
