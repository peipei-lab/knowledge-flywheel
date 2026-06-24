#!/usr/bin/env python3
"""Create a prompt/keyword-driven Xiaohongshu manual research brief.

This intentionally does not automate login, browsing, scraping, or anti-bot
workarounds. It turns a topic into a structured capture checklist and JSON
template for user-provided posts/comments.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "community" / "xiaohongshu_research"


def split_keywords(value: str) -> list[str]:
    words: list[str] = []
    for part in re.split(r"[,，\n]+", value or ""):
        part = part.strip()
        if part and part not in words:
            words.append(part)
    return words


def prompt_keywords(prompt: str) -> list[str]:
    candidates = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+-]{1,}", prompt or "")
    stop = {"怎么", "如何", "什么", "这个", "那个", "关于", "真实", "讨论", "搜索", "帖子", "评论"}
    words: list[str] = []
    for item in candidates:
        if item in stop or item.lower() in {"about", "with", "from", "search"}:
            continue
        if item not in words:
            words.append(item)
    return words[:20]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", default="", help="Comma-separated Xiaohongshu search keywords.")
    parser.add_argument("--prompt", default="", help="Natural-language research intent.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    args = parser.parse_args()

    keywords = split_keywords(args.keywords)
    for word in prompt_keywords(args.prompt):
        if word not in keywords:
            keywords.append(word)
    if not keywords:
        keywords = ["AI育儿", "孩子学习", "职场妈妈", "AI时代教育"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{args.date}-xiaohongshu-research"

    template = [
        {
            "title": "",
            "url": "",
            "search_keyword": "",
            "body": "",
            "likes": "",
            "saves": "",
            "comments": [
                ""
            ],
            "capture_notes": {
                "why_selected": "",
                "high_like_comments": "",
                "debate_points": "",
                "privacy_notes": "不要复制用户隐私细节；评论进入系统前尽量抽象成问题和机制。"
            }
        }
    ]
    json_path = OUT_DIR / f"{stem}-import-template.json"
    json_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

    search_lines = "\n".join(f"- `{word}`" for word in keywords)
    combo_lines = "\n".join(
        f"- `{word} AI` / `{word} 孩子` / `{word} 职场妈妈`" for word in keywords[:8]
    )
    body = f"""# 小红书手动研究任务单：{args.date}

## 研究意图

{args.prompt or "_未提供 prompt，仅使用关键词。_"}

## 建议搜索词

{search_lines}

## 组合搜索词

{combo_lines}

## 每个话题建议捕捉什么

- 3-5 篇高互动帖子：标题、链接、正文概要、点赞/收藏数
- 每篇 5-15 条评论：优先高赞、强共鸣、强反对、具体经验
- 不复制隐私细节，不保留用户名作为分析对象
- 重点记录：真实痛点、争论点、共识、低解法成熟度

## 捕捉标准

- 高频：多个帖子都在讨论类似问题
- 情绪密度：评论里出现焦虑、困惑、反复试错、强共鸣
- 争论价值：评论区有明显不同立场
- Creator 匹配：能被 AI 科学家妈妈视角解释

## 导入模板

填这个 JSON 后运行：

```bash
python3 scripts/import_xiaohongshu.py {json_path}
python3 scripts/sync_capture_vaults.py
python3 scripts/monitor_capture_vault.py --once --no-ai
```

Template: `{json_path}`
"""
    md_path = OUT_DIR / f"{stem}.md"
    md_path.write_text(body, encoding="utf-8")
    print(f"Wrote Xiaohongshu research brief: {md_path}")
    print(f"Wrote import template: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

