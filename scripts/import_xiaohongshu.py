#!/usr/bin/env python3
"""Import manually exported Xiaohongshu posts/comments into community insights.

This avoids automated scraping of login-gated or anti-bot surfaces. Provide a
JSON file, CSV file, or Markdown/text file you saved yourself.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "community" / "xiaohongshu"


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "posts" in data and isinstance(data["posts"], list):
            return data["posts"]
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported JSON shape")


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_text(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [{"title": path.stem, "url": "", "body": text, "comments": []}]


def load_input(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix == ".csv":
        return load_csv(path)
    return load_text(path)


def normalize_post(post: dict[str, Any]) -> dict[str, Any]:
    comments = post.get("comments", [])
    if isinstance(comments, str):
        comments = [part.strip() for part in re.split(r"\n+|\\n+|\|\|", comments) if part.strip()]
    return {
        "title": clean_text(str(post.get("title") or post.get("标题") or "Untitled Xiaohongshu Post")),
        "url": clean_text(str(post.get("url") or post.get("link") or post.get("链接") or "")),
        "author": clean_text(str(post.get("author") or post.get("作者") or "")),
        "body": clean_text(str(post.get("body") or post.get("content") or post.get("正文") or "")),
        "likes": clean_text(str(post.get("likes") or post.get("点赞") or "")),
        "comments": [clean_text(str(comment)) for comment in comments if clean_text(str(comment))],
    }


def write_outputs(date_label: str, source: Path, posts: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_post(post) for post in posts]
    rows = []
    for index, post in enumerate(normalized, 1):
        comment_lines = "\n".join(f"- {comment[:300]}" for comment in post["comments"][:20]) or "- 暂无"
        rows.append(
            f"""## {index}. {post['title']}

- URL: {post['url'] or 'manual import'}
- Likes: {post['likes'] or 'unknown'}
- Boundary: manually provided/imported content; abstract before publishing

### Post Summary

{post['body'][:800] or '_No body provided._'}

### Comments

{comment_lines}

### Creator Triage

- 真实痛点：
- 高频信号：
- 可连接知识原子：
- 可发展选题：
"""
        )

    body = f"""# 小红书帖子与评论导入：{date_label}

Source file: {source}

## 边界

本文件来自你手动保存/导出的内容，不做自动登录抓取。用于个人选题研究时，请把评论抽象成问题和机制，不要直接复制用户表达。

{chr(10).join(rows)}
"""
    out_path = OUT_DIR / f"{date_label}-xiaohongshu-import.md"
    out_path.write_text(body, encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(source),
        "count": len(normalized),
        "posts": normalized,
    }
    manifest_path = OUT_DIR / f"{date_label}-xiaohongshu-import.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote Xiaohongshu import: {out_path}")
    print(f"Wrote manifest: {manifest_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="JSON, CSV, Markdown, or text file manually exported/saved from Xiaohongshu.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    args = parser.parse_args()

    source = Path(args.input_file).resolve()
    if not source.exists():
        raise SystemExit(f"Input file does not exist: {source}")
    write_outputs(args.date, source, load_input(source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

