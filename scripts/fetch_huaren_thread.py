#!/usr/bin/env python3
"""Fetch public Huaren thread posts/comments into privacy-safe insight files."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT_TEMPLATE = ROOT / "prompts" / "thread_comment_insight.md"
OUT_DIR = ROOT / "content" / "community" / "huaren"
PROMPT_DIR = ROOT / "content" / "community" / "prompts"


class ThreadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.posts: list[dict[str, str]] = []
        self._in_h1 = False
        self._in_content = False
        self._current_pid = ""
        self._depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag.lower() == "h1":
            self._in_h1 = True
            self._parts = []
        class_value = attrs_dict.get("class", "")
        if tag.lower() == "div" and "post-content" in class_value.split():
            self._in_content = True
            self._current_pid = attrs_dict.get("data-pid", "") or ""
            self._depth = 1
            self._parts = []
        elif self._in_content and tag.lower() == "div":
            self._depth += 1
        if self._in_content and tag.lower() in {"p", "br", "div"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_h1 or self._in_content:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h1" and self._in_h1:
            self.title = clean_text(" ".join(self._parts))
            self._in_h1 = False
            self._parts = []
        if self._in_content and tag.lower() == "div":
            self._depth -= 1
            if self._depth <= 0:
                text = clean_text("\n".join(self._parts))
                if text:
                    self.posts.append({"pid": self._current_pid, "text": text})
                self._in_content = False
                self._current_pid = ""
                self._parts = []


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CreatorBrandFactory/0.1 (+privacy-safe thread insight)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        content_type = response.headers.get("content-type", "")
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if match:
        charset = match.group(1)
    return raw.decode(charset, errors="replace")


def page_url(url: str, page: int) -> str:
    if page <= 1:
        return url
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query["page"] = [str(page)]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def excerpt(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def parse_int(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else 0


def has_debate_signal(text: str) -> bool:
    return any(
        pattern in text
        for pattern in [
            "但是",
            "不过",
            "问题是",
            "不同意",
            "不一定",
            "没必要",
            "不能",
            "不该",
            "应该",
            "其实",
            "反而",
            "关键",
            "同意",
            "焦虑",
        ]
    )


def classic_score(post: dict[str, str]) -> float:
    text = post.get("text", "")
    likes = parse_int(post.get("likes"))
    return round(likes * 10 + min(len(text) / 120, 5) + (2 if has_debate_signal(text) else 0), 2)


def enrich_posts(posts: list[dict[str, str]], excerpt_chars: int) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for post in posts:
        text = post.get("text", "")
        enriched.append(
            {
                "floor": post["floor"],
                "page": post["page"],
                "pid": post.get("pid", ""),
                "time": post.get("time", ""),
                "likes": parse_int(post.get("likes")),
                "excerpt": excerpt(text, excerpt_chars),
                "char_count": len(text),
                "classic_score": classic_score(post),
                "debate_signal": has_debate_signal(text),
            }
        )
    return enriched


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You extract privacy-safe simplified-Chinese insights from public forum comments.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks).strip()


def parse_thread(url: str, pages: int) -> tuple[str, list[dict[str, str]]]:
    title = ""
    posts: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        markup = fetch(page_url(url, page))
        regex_title = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S | re.I)
        if regex_title and not title:
            title = clean_text(regex_title.group(1))
        regex_posts = parse_posts_from_markup(markup)
        if regex_posts:
            page_posts = regex_posts
        else:
            parser = ThreadParser()
            parser.feed(markup)
            if parser.title and not title:
                title = parser.title
            page_posts = parser.posts
        for post in page_posts:
            key = post.get("pid") or post["text"][:80]
            if key in seen:
                continue
            seen.add(key)
            post["page"] = str(page)
            post["floor"] = str(len(posts) + 1)
            posts.append(post)
    return title, posts


def parse_posts_from_markup(markup: str) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    starts = list(re.finditer(r'<div class="post-item" id="([^"]+)"', markup))
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(markup)
        block = markup[start.start() : end]
        content_match = re.search(r'<div class="post-content"[^>]*data-pid="([^"]*)"[^>]*>(.*?)(?:</div>\s*</div>\s*</div>|<div class="post-item"|<div class="quick-action-row")', block, re.S | re.I)
        if not content_match:
            content_match = re.search(r'<div class="post-content"[^>]*data-pid="([^"]*)"[^>]*>(.*?)</div>\s*</div>', block, re.S | re.I)
        if not content_match:
            continue
        pid = content_match.group(1) or start.group(1)
        text = clean_text(content_match.group(2))
        if not text:
            continue
        likes_match = re.search(r'class="[^"]*\bpraise\b[^"]*".*?<span class="num">(\d+)</span>', block, re.S | re.I)
        time_match = re.search(r'<span class="post-time">([^<]+)</span>', block, re.S | re.I)
        floor_match = re.search(r'<span class="clip-floor"[^>]*>(.*?)<sup>#</sup>', block, re.S | re.I)
        floor_label = clean_text(floor_match.group(1)) if floor_match else ""
        posts.append(
            {
                "pid": pid,
                "text": text,
                "likes": likes_match.group(1) if likes_match else "0",
                "time": clean_text(time_match.group(1)) if time_match else "",
                "floor_label": floor_label,
            }
        )
    return posts


def write_outputs(date_label: str, url: str, title: str, posts: list[dict[str, str]], ai_output: str, excerpt_chars: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    safe_posts = enrich_posts(posts, excerpt_chars)
    classic_posts = sorted(
        [post for post in safe_posts if int(post["floor"]) > 1],
        key=lambda post: (-float(post["classic_score"]), -int(post["likes"]), -int(post["char_count"])),
    )[:8]
    debate_posts = [post for post in classic_posts if post["debate_signal"]]
    prompt = f"""{PROMPT_TEMPLATE.read_text(encoding='utf-8')}

# Thread

- Title: {title}
- URL: {url}

# Privacy-safe excerpts

{json.dumps(safe_posts, ensure_ascii=False, indent=2)}

# Classic reply candidates

{json.dumps(classic_posts, ensure_ascii=False, indent=2)}

# Debate candidates

{json.dumps(debate_posts, ensure_ascii=False, indent=2)}
"""
    prompt_path = PROMPT_DIR / f"{date_label}-huaren-thread-insight-prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    rows = []
    for post in safe_posts:
        rows.append(
            f"""### Floor {post['floor']} / Page {post['page']}

{post['excerpt']}

- Likes: {post['likes']}
- Time: {post['time'] or 'unknown'}
- Char count: {post['char_count']}
- Classic score: {post['classic_score']}
- Debate signal: {post['debate_signal']}
- Triage:
  - 真实痛点：
  - 分歧/共识：
  - 可连接知识原子：
"""
        )
    body = f"""# Huaren 评论区洞察：{title or date_label}

Source: {url}

## 隐私边界

本文件只保存公开帖子页的短摘录和评论洞察。不要直接复制网友个人经历；进入内容创作前，请抽象成问题、机制和 Creator 的原创观点。

## 经典回复候选

{chr(10).join(f"- Floor {post['floor']} | Likes {post['likes']} | Score {post['classic_score']}：{post['excerpt']}" for post in classic_posts) if classic_posts else "_No classic reply candidates._"}

## 争论点候选

{chr(10).join(f"- Floor {post['floor']} | Likes {post['likes']}：{post['excerpt']}" for post in debate_posts) if debate_posts else "_No debate candidates._"}

## 帖子与评论摘录

{chr(10).join(rows) if rows else "_No public posts parsed._"}
"""
    if ai_output:
        body += f"\n\n## AI 评论区洞察\n\n{ai_output}\n"
    out_path = OUT_DIR / f"{date_label}-huaren-thread-comments.md"
    out_path.write_text(body, encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "title": title,
        "post_count": len(posts),
        "excerpt_chars": excerpt_chars,
        "privacy_policy": "short excerpts only; no usernames; use abstraction before publishing",
        "posts": safe_posts,
        "classic_reply_candidates": classic_posts,
        "debate_candidates": debate_posts,
    }
    manifest_path = OUT_DIR / f"{date_label}-huaren-thread-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote Huaren thread comments: {out_path}")
    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote insight prompt: {prompt_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Public Huaren thread URL.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--excerpt-chars", type=int, default=500)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    title, posts = parse_thread(args.url, args.pages)
    prompt_preview = {
        "title": title,
        "url": args.url,
        "posts": enrich_posts(posts, args.excerpt_chars),
    }
    insight_prompt = f"{PROMPT_TEMPLATE.read_text(encoding='utf-8')}\n\n{json.dumps(prompt_preview, ensure_ascii=False, indent=2)}"
    ai_output = "" if args.no_ai else call_openai(insight_prompt, args.model)
    write_outputs(args.date, args.url, title, posts, ai_output, args.excerpt_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
