#!/usr/bin/env python3
"""Convert a weekly brief into knowledge-atom prompt packs or AI output."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATOM_PROMPT = ROOT / "prompts" / "knowledge_atom.md"
KNOWLEDGE = ROOT / "content" / "knowledge"
ATOM_DIR = KNOWLEDGE / "atoms"
PROMPT_DIR = KNOWLEDGE / "prompts"
PROBLEM_BACKLOG = KNOWLEDGE / "problem_backlog" / "problem_backlog.md"


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You structure personal knowledge into concise simplified-Chinese Markdown atoms.",
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
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks).strip()


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "knowledge-atoms"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("brief", help="Path to weekly brief Markdown.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true", help="Only create an AI-ready prompt pack.")
    args = parser.parse_args()

    brief_path = Path(args.brief).resolve()
    if not brief_path.exists():
        raise SystemExit(f"Brief does not exist: {brief_path}")

    date_label = brief_path.stem.replace("-weekly-brief", "") or datetime.now().date().isoformat()
    brief = brief_path.read_text(encoding="utf-8")
    backlog = PROBLEM_BACKLOG.read_text(encoding="utf-8") if PROBLEM_BACKLOG.exists() else ""

    prompt = f"""{ATOM_PROMPT.read_text(encoding='utf-8')}

# 当前 Problem Backlog

{backlog}

# 本周内容

{brief}
"""

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    ATOM_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = PROMPT_DIR / f"{date_label}-knowledge-atom-prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    ai_output = "" if args.no_ai else call_openai(prompt, args.model)
    atom_path = ATOM_DIR / f"{date_label}-knowledge-atoms.md"
    if ai_output:
        atom_path.write_text(ai_output, encoding="utf-8")
    else:
        atom_path.write_text(
            f"""---
type: knowledge_atom_batch
date: {date_label}
status: needs_ai_or_manual_review
source: {brief_path.name}
---

# {date_label} 知识原子草稿

_AI output was not generated. Set `OPENAI_API_KEY` or paste `{prompt_path.name}` into your preferred LLM._

## 手动提取区

### Atom 1: 

## What / 观察现象

## Mechanism / 底层机制

## Plug-in Logic / 可复用插件逻辑
- 育儿场景：
- 职业女性场景：
- Creator 内容创作场景：

## Content Seeds / 可发展选题
- 小红书：
- 长青文章：
- 视频：

## Links / 关联
- 关联问题：
- 关联知识原子：

## Prompt Pack

See: `{prompt_path}`
""",
            encoding="utf-8",
        )

    print(f"Wrote knowledge prompt: {prompt_path}")
    print(f"Wrote knowledge atoms: {atom_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

