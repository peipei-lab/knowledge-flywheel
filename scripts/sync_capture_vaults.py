#!/usr/bin/env python3
"""Sync raw capture files and insight files into two dedicated Obsidian vaults."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
RAW_VAULT = ROOT / "raw_capture_vault"
INSIGHT_VAULT = ROOT / "insight_vault"


RAW_FOLDERS = {
    "index": RAW_VAULT / "00_Index",
    "inbox": RAW_VAULT / "00_Inbox",
    "huaren": RAW_VAULT / "10_Huaren_Raw",
    "xiaohongshu": RAW_VAULT / "20_Xiaohongshu_Raw",
}

INSIGHT_FOLDERS = {
    "index": INSIGHT_VAULT / "00_Index",
    "analyses": INSIGHT_VAULT / "10_Analyses",
    "atoms": INSIGHT_VAULT / "20_Knowledge_Atoms",
    "problems": INSIGHT_VAULT / "30_Problem_Backlog",
    "reflections": INSIGHT_VAULT / "40_Reflections",
}


def ensure_vault(path: Path) -> None:
    (path / ".obsidian").mkdir(parents=True, exist_ok=True)
    app = path / ".obsidian" / "app.json"
    if not app.exists():
        app.write_text('{\n  "legacyEditor": false,\n  "livePreview": true\n}\n', encoding="utf-8")


def copy_markdown(src_dir: Path, dst_dir: Path) -> list[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    if not src_dir.exists():
        return copied
    for src in sorted(src_dir.glob("*.md")):
        dst = dst_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def list_markdown(src_dir: Path) -> list[Path]:
    if not src_dir.exists():
        return []
    return sorted(src_dir.glob("*.md"))


def wiki_links(files: list[Path]) -> str:
    if not files:
        return "- 暂无"
    return "\n".join(f"- [[{path.stem}]]" for path in sorted(files, key=lambda p: p.name))


def write_raw_home(files: dict[str, list[Path]]) -> None:
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"""# Raw Capture Vault

Updated: {updated}

这里专门存 Huaren、小红书、RSS/文章等原始抓取或手动导入结果。这个 vault 的目标是保留证据和上下文，不负责沉淀最终观点。

## Huaren Raw

{wiki_links(files.get("huaren", []))}

## Xiaohongshu Raw

{wiki_links(files.get("xiaohongshu", []))}

## Manual / Curated Inbox

{wiki_links(files.get("inbox", []))}

把你手动保存或在 UI 中提交的高信号 `.md` / `.txt` / `.json` / `.csv` 放到 `00_Inbox`，monitor 会发现并分析。带有 `Source priority: curated` 的内容会在 Review Inbox 中获得更高权重。
"""
    (RAW_VAULT / "Home.md").write_text(body, encoding="utf-8")


def write_insight_home(files: dict[str, list[Path]]) -> None:
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"""# Insight Vault

Updated: {updated}

这里存自动分析结果、知识原子、Problem Backlog 和认知回流。Graph View 主要看这个 vault。

## Analyses

{wiki_links(files.get("analyses", []))}

## Knowledge Atoms

{wiki_links(files.get("atoms", []))}

## Problem Backlog

{wiki_links(files.get("problems", []))}

## Reflections

{wiki_links(files.get("reflections", []))}
"""
    (INSIGHT_VAULT / "Home.md").write_text(body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="")
    args = parser.parse_args()
    _ = args.date

    for folder in RAW_FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)
    for folder in INSIGHT_FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)
    ensure_vault(RAW_VAULT)
    ensure_vault(INSIGHT_VAULT)

    raw_files = {
        "inbox": list_markdown(RAW_FOLDERS["inbox"]),
        "huaren": copy_markdown(CONTENT / "community" / "huaren", RAW_FOLDERS["huaren"]),
        "xiaohongshu": copy_markdown(CONTENT / "community" / "xiaohongshu", RAW_FOLDERS["xiaohongshu"]),
    }
    copied_analyses = copy_markdown(CONTENT / "community" / "analyses", INSIGHT_FOLDERS["analyses"])
    insight_files = {
        "analyses": sorted({*copied_analyses, *list_markdown(INSIGHT_FOLDERS["analyses"])}, key=lambda p: p.name),
        "atoms": copy_markdown(CONTENT / "knowledge" / "atoms", INSIGHT_FOLDERS["atoms"]),
        "problems": copy_markdown(CONTENT / "knowledge" / "problem_backlog", INSIGHT_FOLDERS["problems"]),
        "reflections": copy_markdown(CONTENT / "knowledge" / "reflections", INSIGHT_FOLDERS["reflections"]),
    }
    write_raw_home(raw_files)
    write_insight_home(insight_files)
    print(f"Synced raw capture vault: {RAW_VAULT}")
    print(f"Synced insight vault: {INSIGHT_VAULT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
