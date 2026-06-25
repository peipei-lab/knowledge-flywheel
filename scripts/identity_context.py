"""Helpers for local creator identity context."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_IDENTITY = ROOT / "content" / "identity"
TEMPLATE_IDENTITY = ROOT / "templates" / "identity"
IDENTITY_FILES = ["USER.md", "SOUL.md", "COMMUNICATION.md", "DECISION_RULES.md"]


def init_identity(overwrite: bool = False) -> list[Path]:
    CONTENT_IDENTITY.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in IDENTITY_FILES:
        src = TEMPLATE_IDENTITY / name
        dst = CONTENT_IDENTITY / name
        if not src.exists():
            continue
        if dst.exists() and not overwrite:
            continue
        shutil.copyfile(src, dst)
        written.append(dst)
    return written


def identity_paths() -> list[Path]:
    base = CONTENT_IDENTITY if CONTENT_IDENTITY.exists() else TEMPLATE_IDENTITY
    return [base / name for name in IDENTITY_FILES if (base / name).exists()]


def read_identity_context(limit_per_file: int = 1600) -> str:
    chunks: list[str] = []
    for path in identity_paths():
        chunks.append(f"## {path.name}\n\n{path.read_text(encoding='utf-8')[:limit_per_file]}")
    return "\n\n".join(chunks)
