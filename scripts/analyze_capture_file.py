#!/usr/bin/env python3
"""Analyze one captured community file and write an insight note."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from profile_config import render_profile


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "community" / "analyses"


DEBATE_PATTERNS = [
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
    "我觉得",
    "同意",
    "焦虑",
    "卷",
]


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def excerpt(text: str, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def stable_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:12]


def parse_sections(markdown: str) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            if current_title and current_lines:
                sections.append(section_from_text(current_title, "\n".join(current_lines)))
            current_title = line.strip("# ").strip()
            current_lines = []
        else:
            if current_title:
                current_lines.append(line)
    if current_title and current_lines:
        sections.append(section_from_text(current_title, "\n".join(current_lines)))
    return sections


def section_from_text(title: str, text: str) -> dict[str, object]:
    likes = 0
    like_match = re.search(r"Likes:\s*(\d+)", text)
    if like_match:
        likes = int(like_match.group(1))
    char_count = len(text)
    debate_signal = any(pattern in text for pattern in DEBATE_PATTERNS)
    score = likes * 10 + min(char_count / 120, 5) + (2 if debate_signal else 0)
    return {
        "title": title,
        "text": clean_text(text),
        "excerpt": excerpt(text),
        "likes": likes,
        "char_count": char_count,
        "debate_signal": debate_signal,
        "score": round(score, 2),
    }


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": render_profile("You analyze captured forum/social comments into simplified-Chinese insights for Creator."),
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


def heuristic_analysis(path: Path, text: str, sections: list[dict[str, object]], top_n: int) -> str:
    title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
    classic = sorted(sections, key=lambda item: (-float(item["score"]), -int(item["likes"]), -int(item["char_count"])))[:top_n]
    debates = [item for item in classic if item["debate_signal"]]
    if not debates:
        debates = [item for item in sections if item["debate_signal"]][:top_n]
    pain_keywords = [word for word in ["焦虑", "孩子", "教育", "AI", "职场", "妈妈", "学习", "编程", "时间", "卷"] if word in text]

    classic_lines = "\n".join(
        f"- {item['title']} | likes={item['likes']} | score={item['score']}：{item['excerpt']}" for item in classic
    ) or "- 暂无"
    debate_lines = "\n".join(
        f"- {item['title']}：{item['excerpt']}" for item in debates[:top_n]
    ) or "- 暂无"
    return render_profile(f"""# Capture Analysis: {title}

Source file: {path}
Generated: {datetime.now(timezone.utc).isoformat()}

## 自动结论草稿

这个文件的主要信号词：{", ".join(pain_keywords) if pain_keywords else "待人工判断"}。

## 经典回复候选

{classic_lines}

## 争论点候选

{debate_lines}

## 可进入 Problem Backlog 的问题

- 这个讨论背后的长期问题是什么？
- 它是否体现了妈妈/职业女性在 AI 时代的真实焦虑？
- Creator 可以用哪个科学家妈妈机制解释它？

## 可生成知识原子

### Atom: 待提炼

## What / 观察现象

## Mechanism / 底层机制

## Plug-in Logic / 可复用逻辑

## 内容选题

- 小红书：
- 长青文章：
- 视频：

## 人工补充

> Creator 读完后最真实的判断：
""")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    path = Path(args.input_file).resolve()
    if not path.exists():
        raise SystemExit(f"Input file does not exist: {path}")
    text = clean_text(path.read_text(encoding="utf-8"))
    sections = parse_sections(text)
    prompt = f"""请分析以下抓取/导入内容，提炼经典回复、争论点、真实痛点、Problem Backlog 和知识原子。不要直接复述个人隐私细节。

# Source
{path}

# Content
{text[:12000]}
"""
    ai_output = "" if args.no_ai else call_openai(prompt, args.model)
    body = ai_output or heuristic_analysis(path, text, sections, args.top_n)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}-analysis-{stable_id(path)}.md"
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote analysis: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
