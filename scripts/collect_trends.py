# -*- coding: utf-8 -*-
"""
트렌드 데이터 수집기 (GitHub Actions용, 표준 라이브러리만 사용)
YouTube InnerTube 검색 API를 조회수순으로 호출해 trends_data.json 생성.
로컬 앱(C:\\Users\\User\\zipzip\\trend-viewer\\server.py)과 동일한 로직의 배치 버전.
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(ROOT, "trends_data.json")

INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/search"
INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # 유튜브 웹페이지에 공개 포함된 키
CLIENT_VERSION = "2.20250620.00.00"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CATEGORIES = {
    "음악": "음악 신곡",
    "게임": "게임",
    "먹방": "먹방",
    "뷰티/패션": "뷰티 패션",
    "브이로그": "브이로그",
    "스포츠": "스포츠 하이라이트",
    "예능/코미디": "예능 코미디",
    "영화/드라마": "영화 드라마",
    "테크/IT": "테크 리뷰",
    "지식/교육": "지식 교육",
    "여행": "여행",
    "동물": "강아지 고양이",
    "뉴스/이슈": "뉴스 이슈",
}
PERIOD_MAP = {"today": 2, "week": 3, "month": 4}
LIMIT = 60


def make_params(sort=3, upload=None, vtype=1, duration=None):
    inner = b""
    if upload:
        inner += bytes([0x08, upload])
    if vtype:
        inner += bytes([0x10, vtype])
    if duration:
        inner += bytes([0x18, duration])
    out = bytes([0x08, sort])
    if inner:
        out += bytes([0x12, len(inner)]) + inner
    return base64.b64encode(out).decode()


def innertube_post(body):
    url = INNERTUBE_URL + "?key=" + INNERTUBE_KEY + "&prettyPrint=false"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": CLIENT_VERSION,
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _context():
    return {"client": {
        "clientName": "WEB", "clientVersion": CLIENT_VERSION,
        "hl": "ko", "gl": "KR", "userAgent": USER_AGENT,
    }}


def _walk_collect(obj, key, out):
    if isinstance(obj, dict):
        if key in obj:
            out.append(obj[key])
        for v in obj.values():
            _walk_collect(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_collect(v, key, out)


def _text(node):
    if not node:
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    if "runs" in node:
        return "".join(r.get("text", "") for r in node["runs"])
    return ""


def parse_views(text):
    if not text:
        return 0
    t = text.replace("조회수", "").replace("회", "").replace("views", "").replace("view", "").strip()
    m = re.search(r"([\d,.]+)\s*([억만천KMBkmb]?)", t)
    if not m:
        return 0
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    mult = {"억": 1e8, "만": 1e4, "천": 1e3,
            "K": 1e3, "k": 1e3, "M": 1e6, "m": 1e6, "B": 1e9, "b": 1e9}.get(m.group(2), 1)
    return int(num * mult)


def parse_duration(text):
    if not text:
        return 0
    try:
        parts = [int(p) for p in text.strip().split(":")]
    except ValueError:
        return 0
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _extract_videos(data):
    videos, tokens = [], []
    renderers = []
    _walk_collect(data, "videoRenderer", renderers)
    for r in renderers:
        vid = r.get("videoId")
        if not vid:
            continue
        is_live = False
        for ov in r.get("thumbnailOverlays", []):
            if ov.get("thumbnailOverlayTimeStatusRenderer", {}).get("style", "") == "LIVE":
                is_live = True
        if any(b.get("metadataBadgeRenderer", {}).get("style", "") == "BADGE_STYLE_TYPE_LIVE_NOW"
               for b in r.get("badges", [])):
            is_live = True
        if is_live:
            continue
        dur_text = _text(r.get("lengthText"))
        videos.append({
            "id": vid,
            "title": _text(r.get("title")),
            "channel": _text(r.get("ownerText")) or _text(r.get("longBylineText")),
            "views": parse_views(_text(r.get("viewCountText"))),
            "published": _text(r.get("publishedTimeText")).replace("스트리밍 시간:", "").strip(),
            "duration": dur_text,
            "durationSec": parse_duration(dur_text),
        })
    conts = []
    _walk_collect(data, "continuationItemRenderer", conts)
    for c in conts:
        token = c.get("continuationEndpoint", {}).get("continuationCommand", {}).get("token")
        if token:
            tokens.append(token)
    return videos, tokens


def search_videos(query, period, shorts=False, pages=2):
    params = make_params(sort=3, upload=PERIOD_MAP.get(period, 3), vtype=1,
                         duration=1 if shorts else None)
    body = {"context": _context(), "query": query, "params": params}
    all_videos, token = [], None
    for page in range(pages):
        if page == 0:
            data = innertube_post(body)
        else:
            if not token:
                break
            data = innertube_post({"context": _context(), "continuation": token})
        vids, tokens = _extract_videos(data)
        all_videos.extend(vids)
        token = tokens[0] if tokens else None
    return all_videos


def clean_sort(videos, shorts):
    seen, uniq = set(), []
    for v in videos:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        if shorts and v["durationSec"] > 240:
            continue
        if not shorts and 0 < v["durationSec"] <= 62:
            continue
        # 공동 채널명 현지화("A 및 B", "A 외 2명")의 한글 제거 후 국내 영상 판별
        kr = (v["title"] + " " + v["channel"]).replace(" 및 ", " ")
        kr = re.sub(r"외\s*\d+\s*명", " ", kr)
        if not re.search(r"[가-힣]", kr):
            continue
        uniq.append(v)
    uniq.sort(key=lambda v: v["views"], reverse=True)
    return uniq[:LIMIT]


def slim(videos):
    return [{"id": v["id"], "title": v["title"], "channel": v["channel"],
             "views": v["views"], "published": v["published"],
             "duration": v["duration"]} for v in videos]


def main():
    result = {}
    jobs = []  # (tab, period, category, query)
    for tab in ("youtube", "shorts"):
        for period in PERIOD_MAP:
            for cat, q in CATEGORIES.items():
                jobs.append((tab, period, cat, q))

    fetched = {}
    errors = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(search_videos, q, period, tab == "shorts", 2): (tab, period, cat)
                for tab, period, cat, q in jobs}
        for f in as_completed(futs):
            tab, period, cat = futs[f]
            try:
                fetched[(tab, period, cat)] = f.result()
                print("OK  %s|%s|%s (%d개)" % (tab, period, cat, len(fetched[(tab, period, cat)])))
            except Exception as e:
                errors += 1
                fetched[(tab, period, cat)] = []
                print("FAIL %s|%s|%s: %s" % (tab, period, cat, e))

    for tab in ("youtube", "shorts"):
        for period in PERIOD_MAP:
            merged = []
            for cat in CATEGORIES:
                vids = clean_sort(fetched[(tab, period, cat)], tab == "shorts")
                result["%s|%s|%s" % (tab, period, cat)] = slim(vids)
                merged.extend(vids)
            result["%s|%s|전체" % (tab, period)] = slim(clean_sort(merged, tab == "shorts"))

    total = sum(len(v) for v in result.values())
    if total < 100:
        print("수집 결과가 너무 적습니다 (%d개) — 파일을 갱신하지 않고 실패 처리" % total)
        sys.exit(1)

    out = {
        "generatedAt": int(time.time()),
        "generatedAtText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "categories": ["전체"] + list(CATEGORIES.keys()),
        "data": result,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("저장 완료: %s (%d 데이터셋, 총 %d개 영상, 오류 %d건)"
          % (OUT_FILE, len(result), total, errors))


if __name__ == "__main__":
    main()
