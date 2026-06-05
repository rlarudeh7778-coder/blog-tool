#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""레퍼런스 자동 수집 스크립트.

매일 GitHub Actions(cron)에서 실행되어 ../data.json 의 items 를 새로 채웁니다.
- 유튜브 공식 Data API  (필수: 환경변수 YOUTUBE_API_KEY)
- 레딧 공개 API         (키 불필요)
- 구글 트렌드(pytrends) : 그날의 트렌드 키워드를 유튜브 검색에 추가 (best-effort)

※ 인스타그램/페이스북은 '남들 인기 게시물 검색' 공식 API가 없고 약관상 자동수집이
   금지되어 제외합니다. (필요하면 Apify 같은 유료 스크래퍼로 별도 연동)

각 단계는 실패해도 전체가 죽지 않도록 try/except 로 감싸 '있는 만큼' 수집합니다.
"""
import os
import sys
import json
import html
import datetime
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data.json")

YT_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()

# 카테고리(태그) → 유튜브 검색어 / 레딧 서브레딧
CATEGORIES = {
    "음식/요리":  {"yt": "집밥 레시피",          "subs": ["food", "FoodPorn"]},
    "카페":      {"yt": "감성 카페 추천",         "subs": ["Coffee", "Cafe"]},
    "패션":      {"yt": "데일리룩 코디",          "subs": ["streetwear", "femalefashionadvice"]},
    "뷰티":      {"yt": "메이크업 추천",          "subs": ["MakeupAddiction", "SkincareAddiction"]},
    "여행":      {"yt": "국내여행 브이로그",       "subs": ["travel", "EarthPorn"]},
    "인테리어":   {"yt": "셀프 인테리어",          "subs": ["InteriorDesign", "malelivingspace"]},
    "운동/헬스":  {"yt": "홈트레이닝 루틴",         "subs": ["Fitness", "bodyweightfitness"]},
    "육아":      {"yt": "육아 꿀팁",             "subs": ["Parenting", "NewParents"]},
    "반려동물":   {"yt": "강아지 고양이 꿀팁",      "subs": ["aww", "AnimalsBeingDerps"]},
    "IT/가전":   {"yt": "가성비 전자제품 추천",     "subs": ["gadgets", "BuyItForLife"]},
    "자기계발":   {"yt": "자기계발 루틴",          "subs": ["getdisciplined", "productivity"]},
    "재테크":    {"yt": "재테크 투자 꿀팁",        "subs": ["personalfinance", "investing"]},
}

DAYS_BACK = 21           # 최근 N일 영상만
MAX_PER_CAT_YT = 3       # 카테고리당 유튜브 개수
MAX_PER_CAT_REDDIT = 2   # 카테고리당 레딧 개수
MAX_ITEMS = 120          # data.json 최대 항목 수
UA = "Mozilla/5.0 (compatible; reference-collector/1.0)"


def published_after():
    dt = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_BACK)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- 유튜브 ----------
def yt_search(keyword, n):
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
        "key": YT_KEY, "part": "snippet", "q": keyword, "type": "video",
        "order": "viewCount", "regionCode": "KR", "relevanceLanguage": "ko",
        "publishedAfter": published_after(), "maxResults": n, "safeSearch": "moderate",
    }, timeout=20)
    r.raise_for_status()
    return [it["id"]["videoId"] for it in r.json().get("items", [])
            if it.get("id", {}).get("videoId")]


def yt_stats(ids):
    if not ids:
        return []
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
        "key": YT_KEY, "part": "snippet,statistics", "id": ",".join(ids),
    }, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])


def collect_youtube(keyword, tag, n):
    out = []
    try:
        for v in yt_stats(yt_search(keyword, n)):
            sn, st = v.get("snippet", {}), v.get("statistics", {})
            th = sn.get("thumbnails", {})
            thumb = (th.get("high") or th.get("medium") or th.get("default") or {}).get("url", "")
            title = sn.get("title", "").strip()
            chan = sn.get("channelTitle", "").strip()
            out.append({
                "tag": tag, "source": "youtube", "media": "VIDEO",
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
                "date": sn.get("publishedAt", "")[:10],
                "url": "https://www.youtube.com/watch?v=" + v["id"],
                "thumbnail": thumb,
                "caption": (title + " · " + chan) if chan else title,
            })
    except Exception as e:
        print("  [유튜브] '%s' 실패: %s" % (keyword, e), file=sys.stderr)
    return out


# ---------- 레딧 ----------
def collect_reddit(sub, tag, n):
    out = []
    try:
        r = requests.get("https://www.reddit.com/r/%s/top.json" % sub,
                         params={"t": "day", "limit": 20},
                         headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        for ch in r.json().get("data", {}).get("children", []):
            d = ch.get("data", {})
            if d.get("over_18"):
                continue
            thumb = ""
            try:
                imgs = d.get("preview", {}).get("images", [])
                if imgs:
                    thumb = html.unescape(imgs[0]["source"]["url"])
            except Exception:
                pass
            if not thumb:
                u = d.get("url", "")
                if u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
                    thumb = u
            if not thumb:
                continue  # 이미지 없는 글은 카드가 비므로 제외
            out.append({
                "tag": tag, "source": "reddit",
                "media": "VIDEO" if d.get("is_video") else "IMAGE",
                "likes": int(d.get("ups", 0) or 0),
                "comments": int(d.get("num_comments", 0) or 0),
                "date": datetime.datetime.utcfromtimestamp(
                    d.get("created_utc", 0)).strftime("%Y-%m-%d"),
                "url": "https://www.reddit.com" + d.get("permalink", ""),
                "thumbnail": thumb,
                "caption": "r/%s · %s" % (sub, d.get("title", "").strip()),
            })
            if len(out) >= n:
                break
    except Exception as e:
        print("  [레딧] r/%s 실패: %s" % (sub, e), file=sys.stderr)
    return out


# ---------- 구글 트렌드 (best-effort) ----------
def google_trends(n=5):
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="ko-KR", tz=540)
        df = pt.trending_searches(pn="south_korea")
        return [str(x) for x in df[0].tolist()[:n]]
    except Exception as e:
        print("  [구글트렌드] 건너뜀: %s" % e, file=sys.stderr)
        return []


def main():
    items = []

    if YT_KEY:
        print("유튜브 수집 중...")
        for tag, cfg in CATEGORIES.items():
            items += collect_youtube(cfg["yt"], tag, MAX_PER_CAT_YT)
        trends = google_trends(5)
        if trends:
            print("구글 트렌드 키워드: %s" % ", ".join(trends))
            for kw in trends:
                items += collect_youtube(kw, "트렌드", 2)
    else:
        print("⚠ YOUTUBE_API_KEY 미설정 — 유튜브/트렌드 건너뜀", file=sys.stderr)

    print("레딧 수집 중...")
    for tag, cfg in CATEGORIES.items():
        items += collect_reddit(cfg["subs"][0], tag, MAX_PER_CAT_REDDIT)

    # 중복 제거(url) → 최신순 → 상한
    seen, uniq = set(), []
    for it in items:
        if not it.get("url") or it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    uniq.sort(key=lambda x: x.get("date", ""), reverse=True)
    uniq = uniq[:MAX_ITEMS]

    if not uniq:
        print("⚠ 수집 결과 0건 — 기존 data.json 유지", file=sys.stderr)
        return 0

    for i, it in enumerate(uniq, 1):
        it["id"] = i
    ordered = [{"id": it["id"], "tag": it["tag"], "source": it["source"],
                "media": it["media"], "likes": it["likes"], "comments": it["comments"],
                "date": it["date"], "url": it["url"], "thumbnail": it["thumbnail"],
                "caption": it["caption"]} for it in uniq]

    # 기존 태그 목록 유지(+트렌드)
    base = {}
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            base = {}
    tags = base.get("tags") or list(CATEGORIES.keys())
    if any(it["tag"] == "트렌드" for it in ordered) and "트렌드" not in tags:
        tags = ["트렌드"] + tags

    out = {
        "_README": "이 파일은 GitHub Actions(scripts/collect.py)가 매일 자동 생성합니다. 손으로 고쳐도 다음 실행 때 덮어써집니다.",
        "_generated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "tags": tags,
        "items": ordered,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("✅ %d건 저장 → data.json" % len(ordered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
