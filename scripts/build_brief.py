#!/usr/bin/env python3
"""Build an AI-ready weekly Markdown brief from the inbox."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from profile_config import render_profile


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts" / "weekly_synthesis.md"
BRIEFS = ROOT / "content" / "briefs"


def read_items(inbox_dir: Path) -> str:
    parts = []
    for path in sorted(inbox_dir.glob("*.md")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": render_profile("You are a careful bilingual Chinese editor for Creator's AI personal-brand content workflow."),
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inbox_dir", help="Path to content/inbox/YYYY-MM-DD")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true", help="Only create an AI-ready prompt pack.")
    args = parser.parse_args()

    inbox_dir = Path(args.inbox_dir).resolve()
    if not inbox_dir.exists():
        raise SystemExit(f"Inbox does not exist: {inbox_dir}")

    source_pack = read_items(inbox_dir)
    if not source_pack:
        raise SystemExit(f"No Markdown source files found in {inbox_dir}")

    prompt = f"""{render_profile(PROMPT.read_text(encoding='utf-8'))}

# 本周素材

{source_pack}
"""
    BRIEFS.mkdir(parents=True, exist_ok=True)
    date_label = inbox_dir.name if inbox_dir.name else datetime.now().date().isoformat()
    prompt_path = BRIEFS / f"{date_label}-prompt-pack.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    ai_output = "" if args.no_ai else call_openai(prompt, args.model)
    brief_path = BRIEFS / f"{date_label}-weekly-brief.md"
    if ai_output:
        brief_path.write_text(ai_output, encoding="utf-8")
    else:
        brief_path.write_text(
            render_profile(
            f"""# Creator AI 热点周报草稿：{date_label}

_AI output was not generated. Set `OPENAI_API_KEY` or paste `{prompt_path.name}` into your preferred LLM._

## 人工阅读顺序

1. 先读 `{prompt_path.name}`。
2. 选 1-3 个最有 Creator 观点的素材。
3. 在下方补上科学家妈妈的真实感慨。

## Creator 人工补充区

> 我作为科学家妈妈，这周最想说的是：

## Prompt Pack

See: `{prompt_path}`
"""
            ),
            encoding="utf-8",
        )

    print(f"Wrote prompt pack: {prompt_path}")
    print(f"Wrote weekly brief: {brief_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
