#!/usr/bin/env python3
"""Sync generated Markdown knowledge files into an Obsidian-compatible vault."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from profile_config import creator_name


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
KNOWLEDGE = CONTENT / "knowledge"
VAULT = ROOT / "obsidian_vault"


FOLDERS = {
    "index": VAULT / "00_Index",
    "identity": VAULT / "05_Identity",
    "atoms": VAULT / "10_Knowledge_Atoms",
    "problems": VAULT / "20_Problem_Backlog",
    "reflections": VAULT / "30_Reflections",
    "briefs": VAULT / "40_Content_Briefs",
    "social": VAULT / "50_Social_Drafts",
    "community": VAULT / "60_Community_Insights",
    "pages": VAULT / "70_Pages_Articles",
    "principles": VAULT / "80_Principles",
    "templates": VAULT / "90_Templates",
}


def ensure_dirs() -> None:
    for path in FOLDERS.values():
        path.mkdir(parents=True, exist_ok=True)
    (VAULT / ".obsidian").mkdir(parents=True, exist_ok=True)


def copy_markdown(src_dir: Path, dst_dir: Path) -> list[Path]:
    copied: list[Path] = []
    if not src_dir.exists():
        return copied
    for src in sorted(src_dir.glob("*.md")):
        dst = dst_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def copy_markdown_recursive(src_dir: Path, dst_dir: Path) -> list[Path]:
    copied: list[Path] = []
    if not src_dir.exists():
        return copied
    for src in sorted(src_dir.rglob("*.md")):
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def wiki_links(files: list[Path]) -> str:
    lines = []
    for path in sorted(files, key=lambda p: p.name):
        stem = path.stem
        lines.append(f"- [[{stem}]]")
    return "\n".join(lines) if lines else "- 暂无"


def write_home(all_files: dict[str, list[Path]]) -> None:
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = creator_name()
    body = f"""# {name} 第二大脑

Updated: {updated}

这是 {name} personal branding workflow 自动同步出来的 Obsidian vault。打开这个文件夹后，可以用 Graph View 查看知识原子、问题库、认知回流之间的关系。

## 本周工作台

- [[USER]]
- [[Problem Backlog]]
- [[Knowledge Map]]
- [[Forum Insight Template]]

## 身份与协作方式

{wiki_links(all_files.get("identity", []))}

## 知识原子

{wiki_links(all_files.get("atoms", []))}

## 长期问题库

{wiki_links(all_files.get("problems", []))}

## 每周认知回流

{wiki_links(all_files.get("reflections", []))}

## 内容 Briefs

{wiki_links(all_files.get("briefs", []))}

## 社区洞察

{wiki_links(all_files.get("community", []))}

## Pages 文章草稿/发布稿

{wiki_links(all_files.get("pages", []))}

## 判断原则 / Preference Model

{wiki_links(all_files.get("principles", []))}
"""
    (VAULT / "Home.md").write_text(body, encoding="utf-8")


def write_knowledge_map(all_files: dict[str, list[Path]]) -> None:
    body = f"""# Knowledge Map

## 核心关系

```mermaid
flowchart LR
  Sources[精选信息源] --> Briefs[Weekly Briefs]
  Community[Huaren / Community Signals] --> Problems
  Briefs --> Social[Social Drafts]
  Social --> Pages[Pages Articles]
  Briefs --> Atoms[Knowledge Atoms]
  Atoms --> Problems[Problem Backlog]
  Problems --> Reflections[Cognitive Reflections]
  Reflections --> Topics[Next Topics]
  Feedback[Raw Feedback] --> Principles[Principles / Axioms]
  Identity[Identity Context] --> Principles
  Principles --> Topics
  Topics --> Briefs
```

## 推荐 Obsidian 使用方式

- 打开 Graph View，看哪些知识原子和问题反复连接。
- 给成熟知识原子加 `#evergreen`。
- 给还需要验证的想法加 `#hypothesis`。
- 写文章时先从 [[Problem Backlog]] 找问题，再从知识原子里找机制。

## 当前入口

- [[Home]]
- [[Problem Backlog]]
- [[Forum Insight Template]]
"""
    (FOLDERS["index"] / "Knowledge Map.md").write_text(body, encoding="utf-8")


def write_problem_aliases() -> None:
    backlog = FOLDERS["problems"] / "problem_backlog.md"
    alias = FOLDERS["problems"] / "Problem Backlog.md"
    if backlog.exists():
        text = backlog.read_text(encoding="utf-8")
        if "[[Knowledge Map]]" not in text:
            text += "\n\n## Obsidian Links\n\n- [[Knowledge Map]]\n- [[Home]]\n"
        alias.write_text(text, encoding="utf-8")

    forum = FOLDERS["problems"] / "forum_insight_template.md"
    forum_alias = FOLDERS["templates"] / "Forum Insight Template.md"
    if forum.exists():
        forum_alias.write_text(forum.read_text(encoding="utf-8"), encoding="utf-8")


def write_obsidian_settings() -> None:
    write_if_missing(
        VAULT / ".obsidian" / "app.json",
        '{\n  "legacyEditor": false,\n  "livePreview": true\n}\n',
    )
    write_if_missing(
        VAULT / ".obsidian" / "graph.json",
        '{\n  "collapse-filter": false,\n  "search": "",\n  "showTags": true,\n  "showAttachments": false,\n  "hideUnresolved": false\n}\n',
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Optional date label for future filtering.", default="")
    args = parser.parse_args()
    _ = args.date

    ensure_dirs()
    all_files = {
        "identity": copy_markdown(CONTENT / "identity", FOLDERS["identity"])
        or copy_markdown(ROOT / "templates" / "identity", FOLDERS["identity"]),
        "atoms": copy_markdown(KNOWLEDGE / "atoms", FOLDERS["atoms"]),
        "problems": copy_markdown(KNOWLEDGE / "problem_backlog", FOLDERS["problems"]),
        "reflections": copy_markdown(KNOWLEDGE / "reflections", FOLDERS["reflections"]),
        "briefs": copy_markdown(CONTENT / "briefs", FOLDERS["briefs"]),
        "social": copy_markdown(CONTENT / "social", FOLDERS["social"]),
        "community": copy_markdown(CONTENT / "community" / "huaren", FOLDERS["community"])
        + copy_markdown(CONTENT / "community" / "xiaohongshu", FOLDERS["community"]),
        "pages": copy_markdown_recursive(CONTENT / "pages_drafts", FOLDERS["pages"] / "drafts")
        + copy_markdown_recursive(CONTENT / "pages_published", FOLDERS["pages"] / "published"),
        "principles": copy_markdown(CONTENT / "knowledge" / "principles", FOLDERS["principles"]),
    }
    write_problem_aliases()
    write_home(all_files)
    write_knowledge_map(all_files)
    write_obsidian_settings()

    print(f"Synced Obsidian vault: {VAULT}")
    print(f"Open this folder in Obsidian: {VAULT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
