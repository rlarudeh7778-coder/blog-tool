# -*- coding: utf-8 -*-
"""
영상 다운로더 배포용 ZIP 빌더

바탕화면의 동영상다운로더 폴더를 blog-tool/downloads/video-downloader.zip 으로 묶습니다.
블로그 툴의 downloader.html 설치 안내에서 이 ZIP을 내려받게 됩니다.

사용법:  python scripts/build_downloader_zip.py
"""
import os
import sys
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SRC = Path.home() / "Desktop" / "동영상다운로더"
OUT_DIR = ROOT / "downloads"
OUT_FILE = OUT_DIR / "video-downloader.zip"

# ZIP 안에 들어갈 최상위 폴더명 (압축 풀면 이 이름의 폴더가 생김)
TOP = "영상다운로더"

# 배포에 포함할 파일 (__pycache__ 등은 제외)
FILES = ["server.py", "start.bat", "update.bat", "사용법.md"]


def main():
    if not SRC.is_dir():
        print("원본 폴더를 찾을 수 없습니다: %s" % SRC)
        sys.exit(1)

    missing = [f for f in FILES if not (SRC / f).is_file()]
    if missing:
        print("필수 파일이 없습니다: %s" % ", ".join(missing))
        sys.exit(1)

    # CORS 헤더가 빠진 구버전을 배포하지 않도록 확인
    server_src = (SRC / "server.py").read_text(encoding="utf-8")
    if "Access-Control-Allow-Origin" not in server_src:
        print("server.py에 CORS 헤더가 없습니다 — 블로그 툴 연동이 동작하지 않습니다.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # zipfile은 비ASCII 파일명에 UTF-8 플래그를 자동으로 세팅해 한글 이름이 깨지지 않습니다.
    with zipfile.ZipFile(OUT_FILE, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(SRC / name, "%s/%s" % (TOP, name))

    size_kb = OUT_FILE.stat().st_size / 1024
    print("생성 완료: %s (%d개 파일, %.1f KB)" % (OUT_FILE, len(FILES), size_kb))


if __name__ == "__main__":
    main()
