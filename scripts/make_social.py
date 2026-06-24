#!/usr/bin/env python3
"""Turn a weekly brief into platform-specific draft files."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from profile_config import creator_name, render_profile


ROOT = Path(__file__).resolve().parents[1]
SOCIAL = ROOT / "content" / "social"


def trim(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.strip("# ").strip()
    return f"{creator_name()} AI 热点周报"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("brief", help="Path to weekly brief Markdown")
    args = parser.parse_args()

    brief_path = Path(args.brief).resolve()
    brief = brief_path.read_text(encoding="utf-8")
    date_label = brief_path.stem.replace("-weekly-brief", "") or datetime.now().date().isoformat()
    title = first_heading(brief)

    SOCIAL.mkdir(parents=True, exist_ok=True)

    xhs = f"""# 小红书草稿：{date_label}

## 标题
{trim(title.replace('Creator', '').replace(creator_name(), '').strip('：: '), 28)}

## 封面文案
AI 这周变了什么？
妈妈和职业女性真正要看懂的是这 3 件事

## 正文草稿
{brief}

## 互动问题
你最近最想让 AI 帮你解决的家庭或工作问题是什么？
"""
    twitter = f"""# X/Twitter 长帖草稿：{date_label}

1/ 这周 AI 圈有很多热闹，但我最关心的不是模型名字，而是：它会怎样改变孩子学习、妈妈决策、女性工作的方式？

2/ {trim(brief, 210)}

3/ 我的判断是：真正值得普通人关注的 AI 变化，不是更炫的 demo，而是它是否让我们更会提问、更会判断、更能保留自己的节奏。

4/ 对妈妈来说，AI 不是替孩子走捷径，而是逼我们重新定义：什么能力在未来仍然稀缺？

5/ 对职业女性来说，AI 不是又一个必须追赶的焦虑源，而是一个可以帮我们放大专业判断的工具。

6/ 这周你可以做的一件小事：选一个工作或育儿场景，让 AI 帮你列 5 个更好的问题，而不是直接要答案。
"""
    video = f"""# YouTube / Shorts 口播提纲：{date_label}

## 开头钩子
这周 AI 圈最值得妈妈和职业女性看懂的，不是一个新名词，而是一个更大的变化：我们和知识的关系正在改变。

## 3-5 分钟结构
1. 发生了什么：用一句人话讲清本周最重要变化。
2. 为什么重要：连到孩子学习、妈妈决策、女性职业成长。
3. {creator_name()} 观点：给出清醒判断，不焦虑、不盲从。

## 结尾
这周不要急着追所有热点。选一件和你生活最相关的 AI 变化，问自己：它能不能帮我和孩子更会思考？
"""

    files = {
        SOCIAL / f"{date_label}-xiaohongshu.md": xhs,
        SOCIAL / f"{date_label}-twitter-thread.md": twitter,
        SOCIAL / f"{date_label}-video-outline.md": video,
    }
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
