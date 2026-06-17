#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""일회용: 워드프레스에서 '선불폰' 글만 골라 휴지통으로 보낸다(복구 가능).

애드센스 승인 전, 상업성(전화·오픈채팅 CTA) 글을 정리하기 위한 스크립트.
- 삭제 대상은 autopost_state.json의 log에서 kind=='phone'인 글의 '정확한 제목'.
- 제목이 정확히 일치하는 글만 trash 처리(force 미사용 → 휴지통, 30일 내 복구 가능).
- 안전장치: 제목 정확 일치만 삭제, 매칭 안 되면 건너뛰고 보고만 한다.
- 워드프레스 시크릿(WP_URL/WP_USER/WP_APP_PASSWORD)이 있어야 동작. 없으면 안내 후 종료.

환경변수:
  WP_URL, WP_USER, WP_APP_PASSWORD (필수)
  DRY_RUN=1  (실제 삭제 없이 어떤 글이 매칭되는지 미리보기만)
"""
import os
import sys
import json

import requests

STATE_PATH = os.path.join(os.path.dirname(__file__), "autopost_state.json")

WP_URL = os.environ.get("WP_URL", "").strip().rstrip("/")
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PW = os.environ.get("WP_APP_PASSWORD", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "").strip() == "1"

WP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def phone_titles():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(f"state 읽기 실패: {e}")
        return []
    titles, seen = [], set()
    for e in state.get("log", []):
        if e.get("kind") == "phone":
            t = (e.get("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                titles.append(t)
    return titles


def find_post_ids(title):
    """제목으로 검색해 '정확히 일치'하는 글 id 목록 반환(published+그 외 상태 포함)."""
    url = WP_URL + "/wp-json/wp/v2/posts"
    ids = []
    params = {"search": title, "per_page": 50, "status": "publish,draft,pending,future,private"}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": WP_UA},
                         auth=(WP_USER, WP_APP_PW), timeout=60)
        # status 다중지정이 막히면 기본(publish)로 재시도
        if r.status_code == 400:
            params.pop("status", None)
            r = requests.get(url, params=params, headers={"User-Agent": WP_UA},
                             auth=(WP_USER, WP_APP_PW), timeout=60)
        r.raise_for_status()
        for p in r.json():
            rendered = (p.get("title", {}) or {}).get("rendered", "")
            # 워드프레스가 따옴표 등을 엔티티로 바꿀 수 있어 양쪽 공백만 비교
            if rendered.strip() == title.strip():
                ids.append(p.get("id"))
    except Exception as e:
        print(f"  검색 실패({title}): {e}")
    return ids


def trash_post(pid):
    """force 미사용 → 휴지통(복구 가능)."""
    url = WP_URL + f"/wp-json/wp/v2/posts/{pid}"
    r = requests.delete(url, headers={"User-Agent": WP_UA},
                        auth=(WP_USER, WP_APP_PW), timeout=60)
    r.raise_for_status()
    return r.json().get("status")


def main():
    if not (WP_URL and WP_USER and WP_APP_PW):
        print("⏭ 워드프레스 시크릿(WP_URL/WP_USER/WP_APP_PASSWORD) 미설정 — 종료.")
        sys.exit(0)

    titles = phone_titles()
    print(f"▶ 선불폰 글 {len(titles)}편 정리 시작 | DRY_RUN={DRY_RUN}")
    trashed = 0
    not_found = []
    for t in titles:
        ids = find_post_ids(t)
        if not ids:
            not_found.append(t)
            print(f"  · 매칭 없음(이미 삭제됐거나 제목 변경?): {t}")
            continue
        for pid in ids:
            if DRY_RUN:
                print(f"  · (DRY_RUN) 휴지통 예정 id={pid}: {t}")
            else:
                try:
                    st = trash_post(pid)
                    print(f"  ✓ 휴지통 이동 id={pid} (status={st}): {t}")
                    trashed += 1
                except Exception as e:
                    print(f"  ✗ 삭제 실패 id={pid}: {e}")
    print(f"■ 완료: {'(미리보기) ' if DRY_RUN else ''}휴지통 {trashed}편, 매칭 없음 {len(not_found)}편.")


if __name__ == "__main__":
    main()
