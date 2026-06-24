#!/usr/bin/env python3
"""Create a weekly cognitive reflection from atoms, briefs, and problem backlog."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from profile_config import render_profile


ROOT = Path(__file__).resolve().parents[1]
REFLECTION_PROMPT = ROOT / "prompts" / "cognitive_reflection.md"
KNOWLEDGE = ROOT / "content" / "knowledge"
ATOM_DIR = KNOWLEDGE / "atoms"
REFLECTION_DIR = KNOWLEDGE / "reflections"
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
                "content": render_profile("You are Creator's simplified-Chinese cognitive reflection assistant."),
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


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("date_label", help="Date label used by the weekly run, e.g. YYYY-MM-DD.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true", help="Only create an AI-ready prompt pack.")
    args = parser.parse_args()

    date_label = args.date_label or datetime.now().date().isoformat()
    brief = read_optional(ROOT / "content" / "briefs" / f"{date_label}-weekly-brief.md")
    atoms = read_optional(ATOM_DIR / f"{date_label}-knowledge-atoms.md")
    backlog = read_optional(PROBLEM_BACKLOG)

    if not brief and not atoms:
        raise SystemExit(f"No weekly brief or knowledge atoms found for {date_label}")

    prompt = f"""{render_profile(REFLECTION_PROMPT.read_text(encoding='utf-8'))}

# Problem Backlog

{backlog}

# 本周 Weekly Brief

{brief}

# 本周 Knowledge Atoms

{atoms}
"""

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = PROMPT_DIR / f"{date_label}-cognitive-reflection-prompt.md"
    reflection_path = REFLECTION_DIR / f"{date_label}-cognitive-reflection.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    ai_output = "" if args.no_ai else call_openai(prompt, args.model)
    if ai_output:
        reflection_path.write_text(ai_output, encoding="utf-8")
    else:
        reflection_path.write_text(
            render_profile(
            f"""# {date_label} 本周认知回流报告

_AI output was not generated. Set `OPENAI_API_KEY` or paste `{prompt_path.name}` into your preferred LLM._

## 1. 本周 Creator 的观点进化

## 2. 新知识原子可以 Plug-in 到哪里

## 3. 与 Problem Backlog 的匹配

## 4. 跨领域联想

## 5. 下周最值得追踪的 3 个问题

## 6. 给 Creator 的 5 分钟自我更新

## Prompt Pack

See: `{prompt_path}`
"""
            ),
            encoding="utf-8",
        )

    print(f"Wrote reflection prompt: {prompt_path}")
    print(f"Wrote cognitive reflection: {reflection_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
