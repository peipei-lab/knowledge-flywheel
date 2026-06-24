#!/usr/bin/env python3
"""Search public-domain/open ebook sources and optionally download a selected book."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_SEARCH = ROOT / "content" / "books" / "searches"
OUT_RAW = ROOT / "content" / "books" / "raw"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CreatorBrandFactory/0.1 (+public-domain ebook research)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CreatorBrandFactory/0.1 (+public-domain ebook research)"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "ebook"


def search_gutenberg(query: str, limit: int) -> list[dict]:
    url = "https://gutendex.com/books?" + urllib.parse.urlencode({"search": query})
    data = fetch_json(url)
    results = []
    for item in data.get("results", [])[:limit]:
        formats = item.get("formats", {})
        text_url = next(
            (formats[key] for key in formats if key.startswith("text/plain") and ".zip" not in formats[key]),
            "",
        )
        epub_url = formats.get("application/epub+zip", "")
        results.append(
            {
                "id": f"gutenberg-{item.get('id')}",
                "source": "Project Gutenberg",
                "title": item.get("title", ""),
                "authors": [author.get("name", "") for author in item.get("authors", [])],
                "subjects": item.get("subjects", []),
                "languages": item.get("languages", []),
                "download_count": item.get("download_count", 0),
                "text_url": text_url,
                "epub_url": epub_url,
                "rights": "public domain / Project Gutenberg metadata",
            }
        )
    return results


def write_search(date_label: str, query: str, results: list[dict]) -> Path:
    OUT_SEARCH.mkdir(parents=True, exist_ok=True)
    path = OUT_SEARCH / f"{date_label}-ebook-search.md"
    rows = []
    for index, item in enumerate(results, 1):
        rows.append(
            f"""## {index}. {item['title']}

- ID: {item['id']}
- Source: {item['source']}
- Authors: {', '.join(item['authors']) or 'unknown'}
- Languages: {', '.join(item['languages'])}
- Downloads: {item['download_count']}
- Text URL: {item['text_url'] or 'none'}
- EPUB URL: {item['epub_url'] or 'none'}
- Rights: {item['rights']}
- Creator relevance:
"""
        )
    body = f"""# Public Ebook Search: {query}

Generated: {datetime.now(timezone.utc).isoformat()}

## Legal Boundary

Only download public-domain, open-license, open-access, or user-owned books. Do not use this workflow to search for pirated copyrighted ebooks.

{chr(10).join(rows) if rows else '_No results._'}
"""
    path.write_text(body, encoding="utf-8")
    (OUT_SEARCH / f"{date_label}-ebook-search.json").write_text(
        json.dumps({"query": query, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def download_book(book_id: str, results: list[dict], prefer: str) -> Path:
    match = next((item for item in results if item["id"] == book_id), None)
    if not match:
        raise SystemExit(f"Book id not found in search results: {book_id}")
    url = match.get("text_url") if prefer == "txt" else match.get("epub_url") or match.get("text_url")
    if not url:
        raise SystemExit(f"No downloadable {prefer} URL for {book_id}")
    OUT_RAW.mkdir(parents=True, exist_ok=True)
    suffix = ".txt" if url == match.get("text_url") else ".epub"
    path = OUT_RAW / f"{slugify(match['title'])}-{book_id}{suffix}"
    path.write_bytes(fetch_bytes(url))
    meta_path = OUT_RAW / f"{slugify(match['title'])}-{book_id}.json"
    meta_path.write_text(json.dumps(match, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Search query or topic keywords.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--download-id", help="Optional result id to download, e.g. gutenberg-1342.")
    parser.add_argument("--prefer", choices=["txt", "epub"], default="txt")
    args = parser.parse_args()

    results = search_gutenberg(args.query, args.limit)
    search_path = write_search(args.date, args.query, results)
    print(f"Wrote search results: {search_path}")
    if args.download_id:
        book_path = download_book(args.download_id, results, args.prefer)
        print(f"Downloaded book: {book_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

