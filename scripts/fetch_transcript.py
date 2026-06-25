#!/usr/bin/env python3
"""Fetch existing YouTube/podcast transcripts when public captions are available."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_YTDLP = ROOT / ".venv" / "bin" / "yt-dlp"


def clean_caption_text(text: str) -> str:
    lines: list[str] = []
    previous = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if "-->" in line or re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines).strip()


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "knowledge-flywheel/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
        content_type = response.headers.get_content_charset() or "utf-8"
    return data.decode(content_type, errors="replace")


def yt_dlp_bin() -> str:
    if LOCAL_YTDLP.exists():
        return str(LOCAL_YTDLP)
    found = shutil.which("yt-dlp")
    if found:
        return found
    raise SystemExit(
        "YouTube transcript fetch requires yt-dlp. Install it with: "
        "python3 -m pip install yt-dlp"
    )


def fetch_youtube(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="knowledge-flywheel-youtube-") as tmp:
        output = str(Path(tmp) / "%(id)s.%(ext)s")
        cmd = [
            yt_dlp_bin(),
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "en,zh-Hans,zh-CN,zh",
            "--sub-format",
            "vtt",
            "--output",
            output,
            url,
        ]
        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode != 0:
            raise SystemExit(result.stderr or result.stdout or "yt-dlp failed to fetch captions.")
        caption_files = sorted(Path(tmp).glob("*.vtt"))
        if not caption_files:
            raise SystemExit("No public captions or auto-captions were found for this YouTube video.")
        return clean_caption_text(caption_files[0].read_text(encoding="utf-8", errors="replace"))


def transcript_url_from_page(url: str, page: str) -> str:
    patterns = [
        r"<podcast:transcript[^>]+url=[\"']([^\"']+)[\"']",
        r"<transcript[^>]+url=[\"']([^\"']+)[\"']",
        r"href=[\"']([^\"']*(?:transcript|captions|subtitles)[^\"']*\.(?:txt|vtt|srt))",
        r"url=[\"']([^\"']*\.(?:txt|vtt|srt))",
    ]
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.I)
        if match:
            return urllib.parse.urljoin(url, match.group(1))
    return ""


def fetch_podcast(url: str) -> str:
    if re.search(r"\.(txt|vtt|srt)(?:\?|$)", url, flags=re.I):
        return clean_caption_text(fetch_url(url))
    page = fetch_url(url)
    transcript_url = transcript_url_from_page(url, page)
    if not transcript_url:
        raise SystemExit(
            "No public podcast transcript link was found. Paste a transcript manually, "
            "or use a direct .txt/.vtt/.srt transcript URL."
        )
    return clean_caption_text(fetch_url(transcript_url))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-type", choices=["youtube", "podcast"], required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    text = fetch_youtube(args.url) if args.source_type == "youtube" else fetch_podcast(args.url)
    if args.json:
        print(json.dumps({"text": text}, ensure_ascii=False))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
