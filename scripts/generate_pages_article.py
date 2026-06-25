#!/usr/bin/env python3
"""Generate bilingual GitHub Pages article drafts from a reviewed candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from profile_config import creator_name, feedback_dir_name, render_profile


ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "insight_vault" / "60_Review_Inbox"
CANDIDATES_PATH = INBOX / "candidates.jsonl"
FEEDBACK_EVENTS = ROOT / "insight_vault" / feedback_dir_name() / "raw_feedback_events.jsonl"
DRAFTS = ROOT / "content" / "pages_drafts"
CODEX_TASKS = ROOT / "content" / "codex_tasks" / "translation_requests"
REVISIONS = ROOT / "insight_vault" / "70_Draft_Revisions"


def slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in value).strip().lower()
    return "-".join(safe.split())[:88] or "untitled"


def load_candidates() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not CANDIDATES_PATH.exists():
        return rows
    for line in CANDIDATES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows[str(item.get("candidate_id", ""))] = item
    return rows


def latest_feedback(candidate_id: str) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    feedback_paths = sorted((ROOT / "insight_vault").glob("30_*_Feedback/raw_feedback_events.jsonl"))
    if FEEDBACK_EVENTS not in feedback_paths:
        feedback_paths.append(FEEDBACK_EVENTS)
    for path in feedback_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(event.get("item_id")) == candidate_id:
                latest = event
    return latest


def read_source(candidate: dict[str, Any]) -> str:
    source = str(candidate.get("source_path") or "")
    path = ROOT / source
    if source and path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def call_openai(prompt: str, model: str, system: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.loads(response.read().decode("utf-8"))
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks).strip()


def frontmatter(title: str, slug: str, lang: str, date_label: str, status: str) -> str:
    escaped_title = title.replace('"', '\\"')
    return f"""---
layout: post
title: "{escaped_title}"
date: {date_label}
lang: {lang}
ref: {slug}
status: {status}
---
"""


def fallback_zh(candidate: dict[str, Any], source_text: str, feedback: dict[str, Any]) -> str:
    title = str(candidate.get("title") or "未命名文章")
    raw_feedback = str(feedback.get("raw_feedback_text") or "")
    rewrite = str(feedback.get("rewrite_instruction") or "")
    return render_profile(f"""# {title}

> 这是一版可人工继续修改的 Pages 中文草稿。没有检测到 `OPENAI_API_KEY`，所以系统先生成结构化初稿，而不是假装已经完成深度写作。

## 开场

最近我在看一个关于 AI 知识库和第二大脑的讨论。它真正打动我的地方，不是某个工具或模板，而是一个更底层的问题：我们到底是在建立知识，还是在建立一个更漂亮的收藏夹？

## 核心观点

{candidate.get("summary") or "待补充。"}

## 底层机制

{candidate.get("mechanism") or "真正有价值的不是自动整理，而是人的判断、提问和持续反馈。"}

## Creator 视角

我越来越觉得，AI 最适合接管的不是我们的判断，而是那些消耗判断之前的体力活：搜索、抓取、整理、对比、归档。人的角色反而应该被抬高：我来决定什么值得看，什么值得保留，什么值得改写，什么根本不值得进入我的思想系统。

这和育儿、女性职业发展、人生选择其实是同一个问题。未来真正稀缺的不是拥有更多信息，而是能不能在信息很多的时候，依然保持自己的判断。

## 可以立刻做的一件小事

每次读到一条想收藏的内容，先问三个问题：

1. 哪一句话真正触动了我？
2. 它为什么触动我，和我的经历、孩子、职业或人生选择有什么关系？
3. 我接下来可以做的一件小事是什么？

## 你的上一轮反馈

{raw_feedback or "_暂无人工反馈。_"}

## 下一轮改写指令

{rewrite or "_暂无改写指令。_"}

## Source Notes

{source_text[:2400].strip() or "_No source analysis found._"}
""")


def build_prompt(candidate: dict[str, Any], source_text: str, feedback: dict[str, Any]) -> str:
    return render_profile(f"""请基于下面的候选分析和 Creator 的人工反馈，写一篇准备发布到 GitHub Pages 的中文长文。

要求：
- 主题范围：AI x 育儿 x 女性职业 x 人生思考。
- 不要写成工具教程，要写成有判断、有生活真实感、有科学家妈妈视角的文章。
- 保留机制洞察，但用普通人能懂的话表达。
- 不直接复制论坛/小红书评论，只抽象成问题、矛盾和洞察。
- 结构清晰，有标题、开场、核心论点、Creator 视角、行动建议。
- 结尾不要鸡汤，要给一个可以立刻做的小动作。

候选：
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Creator 最新反馈：
{json.dumps(feedback, ensure_ascii=False, indent=2)}

源分析：
{source_text}
""")


def translation_prompt(title: str, zh_article: str) -> str:
    return render_profile(f"""Translate and culturally adapt this Chinese article into natural English for GitHub Pages.

Rules:
- Preserve Creator's voice: thoughtful, precise, warm, not hype-driven.
- Keep AI/parenting/women-career/life-reflection framing.
- Do not sound like a literal translation.
- Keep Markdown structure.

Title: {title}

Chinese article:
{zh_article}
""")


def write_codex_translation_request(slug: str, title: str, zh_path: Path, en_path: Path, prompt_path: Path) -> Path:
    CODEX_TASKS.mkdir(parents=True, exist_ok=True)
    request_path = CODEX_TASKS / f"{slug}-translation-request.md"
    request_path.write_text(
        render_profile(
            f"""# Codex Translation Request: {title}

Status: pending
Created: {datetime.now(timezone.utc).isoformat()}
Slug: {slug}

## Task

Please translate and culturally adapt the Chinese draft into a natural English GitHub Pages article.

## Requirements

- Preserve Creator's voice: thoughtful, precise, warm, and not hype-driven.
- Keep the AI x parenting x women's career x life-reflection framing when relevant.
- Do not translate internal `Source Notes`, local filesystem paths, raw excerpts, or private workflow metadata into the public article.
- Keep YAML frontmatter in the English output.
- Write the final English draft back to the target file.

## Source Chinese Draft

`{zh_path.relative_to(ROOT)}`

## Target English Draft

`{en_path.relative_to(ROOT)}`

## Translation Prompt

`{prompt_path.relative_to(ROOT)}`
"""
        ),
        encoding="utf-8",
    )
    return request_path


def archive_version(slug: str, zh_path: Path, en_path: Path, prompt_path: Path) -> None:
    article_dir = REVISIONS / slug
    article_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(article_dir.glob("v*-pages-zh.md"))
    version = f"v{len(existing) + 1:02d}"
    (article_dir / f"{version}-pages-zh.md").write_text(zh_path.read_text(encoding="utf-8"), encoding="utf-8")
    (article_dir / f"{version}-pages-en.md").write_text(en_path.read_text(encoding="utf-8"), encoding="utf-8")
    (article_dir / f"{version}-generation-prompt.md").write_text(prompt_path.read_text(encoding="utf-8"), encoding="utf-8")
    summary = article_dir / "revision_summary.md"
    if not summary.exists():
        summary.write_text(
            f"""# Revision Summary: {slug}

| Version | Chinese draft | English draft | Prompt |
|---|---|---|---|
""",
            encoding="utf-8",
        )
    with summary.open("a", encoding="utf-8") as handle:
        handle.write(f"| {version} | {zh_path.relative_to(ROOT)} | {en_path.relative_to(ROOT)} | {prompt_path.relative_to(ROOT)} |\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--title")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    candidates = load_candidates()
    candidate = candidates.get(args.candidate_id)
    if not candidate:
        raise SystemExit(f"Candidate not found: {args.candidate_id}")

    title = args.title or str(candidate.get("title") or f"{creator_name()} AI Notes")
    slug_seed = args.slug or f"{args.date}-{title}"
    slug = slugify(slug_seed)
    source_text = read_source(candidate)
    feedback = latest_feedback(args.candidate_id)
    prompt = build_prompt(candidate, source_text, feedback)

    article_dir = DRAFTS / slug
    article_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = article_dir / "generation-prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    zh_body = "" if args.no_ai else call_openai(
        prompt,
        args.model,
        render_profile("You are Creator's bilingual editor. Write polished Simplified Chinese Markdown articles."),
    )
    if not zh_body:
        zh_body = fallback_zh(candidate, source_text, feedback)

    zh_path = article_dir / f"{args.date}-{slug}.zh.md"
    zh_path.write_text(frontmatter(title, slug, "zh", args.date, "draft") + "\n" + zh_body.strip() + "\n", encoding="utf-8")

    en_prompt = translation_prompt(title, zh_body)
    en_prompt_path = article_dir / "translation-prompt.md"
    en_prompt_path.write_text(en_prompt, encoding="utf-8")
    en_body = "" if args.no_ai else call_openai(
        en_prompt,
        args.model,
        render_profile("You are a careful English editor translating Creator's Chinese essays for an international audience."),
    )
    if not en_body:
        en_body = f"""# {title}

_English translation pending. This draft has been routed to the local Codex translation queue._

## Chinese Draft Reference

See `{zh_path.name}` in the same draft folder.
"""
    en_title = title if en_body.startswith("# ") else title
    en_path = article_dir / f"{args.date}-{slug}.en.md"
    en_path.write_text(frontmatter(en_title, slug, "en", args.date, "draft") + "\n" + en_body.strip() + "\n", encoding="utf-8")
    request_path = None
    if "English translation pending" in en_body:
        request_path = write_codex_translation_request(slug, title, zh_path, en_path, en_prompt_path)

    archive_version(slug, zh_path, en_path, prompt_path)
    digest = hashlib.sha256((zh_body + en_body).encode("utf-8")).hexdigest()[:12]
    print(f"Generated bilingual Pages draft: {article_dir}")
    print(f"Chinese: {zh_path}")
    print(f"English: {en_path}")
    if request_path:
        print(f"Codex translation request: {request_path}")
    print(f"Draft digest: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
