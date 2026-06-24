#!/usr/bin/env python3
"""Sync ebook raw files and chapter analyses into an Obsidian-compatible book vault."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "books"
VAULT = ROOT / "book_vault"


FOLDERS = {
    "index": VAULT / "00_Index",
    "raw": VAULT / "10_Raw_Books",
    "analyses": VAULT / "20_Chapter_Analyses",
    "atoms": VAULT / "30_Knowledge_Atoms",
    "socratic": VAULT / "40_Socratic_Notes",
    "notebooklm": VAULT / "50_NotebookLM_Outputs",
}


def ensure() -> None:
    for folder in FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)
    (VAULT / ".obsidian").mkdir(parents=True, exist_ok=True)
    app = VAULT / ".obsidian" / "app.json"
    if not app.exists():
        app.write_text('{\n  "legacyEditor": false,\n  "livePreview": true\n}\n', encoding="utf-8")


def copy_files(src: Path, dst: Path, suffixes: tuple[str, ...]) -> list[Path]:
    copied: list[Path] = []
    if not src.exists():
        return copied
    for path in sorted(src.iterdir()):
        if path.is_file() and path.suffix.lower() in suffixes:
            target = dst / path.name
            shutil.copy2(path, target)
            copied.append(target)
    return copied


def wiki_links(files: list[Path]) -> str:
    md = [path for path in files if path.suffix.lower() == ".md"]
    if not md:
        return "- 暂无"
    return "\n".join(f"- [[{path.stem}]]" for path in md)


def main() -> int:
    ensure()
    raw = copy_files(CONTENT / "raw", FOLDERS["raw"], (".txt", ".epub", ".md", ".json"))
    analyses = copy_files(CONTENT / "analyses", FOLDERS["analyses"], (".md",))
    notebooklm = copy_files(VAULT / "50_NotebookLM_Outputs", FOLDERS["notebooklm"], (".md",))
    body = f"""# Book Vault

Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

这个 vault 专门存电子书、章节分析、知识原子和苏格拉底式问题链。

## Raw Books

{wiki_links(raw)}

## Chapter Analyses

{wiki_links(analyses)}

## NotebookLM Outputs

{wiki_links(notebooklm)}

## Workflow

1. Search public-domain/open books with `search_public_ebooks.py`.
2. Analyze chapters with `analyze_ebook.py`.
3. Sync here with `sync_book_vault.py`.

## Optional NotebookLM Adapter

If you install and authenticate the unofficial `notebooklm-py` CLI, `notebooklm_adapter.py` can save NotebookLM outputs here.
"""
    (VAULT / "Home.md").write_text(body, encoding="utf-8")
    print(f"Synced book vault: {VAULT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
