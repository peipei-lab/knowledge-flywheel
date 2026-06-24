#!/usr/bin/env python3
"""Search public Huaren forum listing pages by keywords or a user prompt.

This script intentionally collects metadata only: title, URL, forum, rough
reply/view counts when visible, and matching keywords. It does not fetch full
thread bodies by default.
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "huaren_forums.json"
PROMPT_TEMPLATE = ROOT / "prompts" / "community_insight.md"
OUT_DIR = ROOT / "content" / "community" / "huaren"
PROMPT_DIR = ROOT / "content" / "community" / "prompts"


STOPWORDS = {
    "一个",
    "一些",
    "这个",
    "那个",
    "怎么",
    "如何",
    "什么",
    "是不是",
    "有没有",
    "可以",
    "觉得",
    "就是",
    "以及",
    "或者",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "how",
    "what",
    "why",
}


@dataclass
class Link:
    href: str
    text: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[Link] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href")
            if href:
                self._href = href
                self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = clean_text(" ".join(self._parts))
            if text:
                self.links.append(Link(self._href, text))
            self._href = None
            self._parts = []


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ·\t\n\r")


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CreatorBrandFactory/0.1 (+metadata-only community insight)",
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


def extract_prompt_keywords(prompt: str, defaults: list[str]) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+-]{1,}", prompt)
    keywords: list[str] = []
    for word in words:
        normalized = word.strip()
        if not normalized or normalized.lower() in STOPWORDS or normalized in STOPWORDS:
            continue
        if normalized not in keywords:
            keywords.append(normalized)
    for word in defaults:
        if word in prompt and word not in keywords:
            keywords.append(word)
    return keywords[:20]


def parse_keywords(args: argparse.Namespace, defaults: list[str]) -> list[str]:
    keywords: list[str] = []
    if args.keywords:
        for part in re.split(r"[,，\n]+", args.keywords):
            part = part.strip()
            if part:
                keywords.append(part)
    if args.prompt:
        for word in extract_prompt_keywords(args.prompt, defaults):
            if word not in keywords:
                keywords.append(word)
    if not keywords:
        keywords = defaults[:]
    return keywords


def normalize_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def is_thread_url(url: str) -> bool:
    return "showtopic.html" in url or "topic.html" in url


def score_title(title: str, keywords: list[str]) -> tuple[int, list[str]]:
    title_lower = title.lower()
    matched = []
    score = 0
    for keyword in keywords:
        if keyword.lower() in title_lower:
            matched.append(keyword)
            score += 2 if len(keyword) >= 3 else 1
    return score, matched


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def search_forum(config: dict[str, Any], forum: dict[str, Any], keywords: list[str], pages: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        url = page_url(forum["url"], page)
        markup = fetch(url)
        parser = LinkParser()
        parser.feed(markup)
        for link in parser.links:
            absolute = normalize_url(config["base_url"], link.href)
            if not is_thread_url(absolute):
                continue
            title = clean_text(link.text)
            if len(title) < 4 or absolute in seen:
                continue
            score, matched = score_title(title, keywords)
            if score <= 0:
                continue
            seen.add(absolute)
            results.append(
                {
                    "id": stable_id(absolute),
                    "forum_id": forum["id"],
                    "forum_name": forum["name"],
                    "forum_angle": forum.get("angle", ""),
                    "title": title,
                    "url": absolute,
                    "matched_keywords": matched,
                    "score": score + max(0, 3 - int(forum.get("priority", 3))),
                    "source_boundary": "public listing metadata only; read manually before quoting or summarizing",
                }
            )
    return results


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You analyze public forum metadata into privacy-safe simplified-Chinese community insights.",
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


def write_outputs(date_label: str, keywords: list[str], prompt_text: str, results: list[dict[str, Any]], ai_output: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": keywords,
        "prompt": prompt_text,
        "count": len(results),
        "results": results,
    }
    manifest_path = OUT_DIR / f"{date_label}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for index, item in enumerate(results, 1):
        rows.append(
            f"""### {index}. {item['title']}

- Forum: {item['forum_name']}
- URL: {item['url']}
- Matched keywords: {', '.join(item['matched_keywords'])}
- Score: {item['score']}
- Boundary: {item['source_boundary']}
- Creator triage:
  - 是否值得手动阅读：
  - 背后的真实问题：
  - 可连接知识原子：
"""
        )

    markdown = f"""# Huaren 候选论坛洞察：{date_label}

## 搜索输入

- Keywords: {", ".join(keywords)}
- Prompt: {prompt_text or "_none_"}

## 隐私边界

本文件只保存公开列表页元数据。不要直接复制网友原文；如果要进入知识库，请用自己的话抽象成问题、机制和内容选题。

## 候选帖子

{chr(10).join(rows) if rows else "_No matching public listing results._"}
"""
    if ai_output:
        markdown += f"\n\n## AI 社区洞察\n\n{ai_output}\n"

    (OUT_DIR / f"{date_label}-huaren-candidates.md").write_text(markdown, encoding="utf-8")

    insight_prompt = f"""{PROMPT_TEMPLATE.read_text(encoding='utf-8')}

# 用户搜索意图

{prompt_text or ", ".join(keywords)}

# 候选帖子元数据

{json.dumps(results, ensure_ascii=False, indent=2)}
"""
    (PROMPT_DIR / f"{date_label}-huaren-insight-prompt.md").write_text(insight_prompt, encoding="utf-8")
    print(f"Wrote Huaren candidates: {OUT_DIR / f'{date_label}-huaren-candidates.md'}")
    print(f"Wrote Huaren manifest: {manifest_path}")
    print(f"Wrote insight prompt: {PROMPT_DIR / f'{date_label}-huaren-insight-prompt.md'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", help="Comma-separated keywords, e.g. 孩子,AI,职场")
    parser.add_argument("--prompt", help="A natural-language search intent. Keywords will be extracted locally.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--pages", type=int, help="Pages per forum. Defaults to config.")
    parser.add_argument("--max-results", type=int, help="Max candidate results. Defaults to config.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true", help="Only create candidate list and AI-ready prompt.")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    keywords = parse_keywords(args, config.get("default_lenses", []))
    pages = args.pages or int(config.get("pages_per_forum", 2))
    max_results = args.max_results or int(config.get("max_results", 30))
    min_score = int(config.get("min_score", 1))

    results: list[dict[str, Any]] = []
    for forum in sorted(config["forums"], key=lambda item: item.get("priority", 99)):
        results.extend(search_forum(config, forum, keywords, pages))

    deduped = {item["url"]: item for item in results}
    ranked = sorted(deduped.values(), key=lambda item: (-item["score"], item["forum_name"], item["title"]))
    ranked = [item for item in ranked if item["score"] >= min_score][:max_results]

    insight_prompt = f"{PROMPT_TEMPLATE.read_text(encoding='utf-8')}\n\n{json.dumps(ranked, ensure_ascii=False, indent=2)}"
    ai_output = "" if args.no_ai else call_openai(insight_prompt, args.model)
    write_outputs(args.date, keywords, args.prompt or "", ranked, ai_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

