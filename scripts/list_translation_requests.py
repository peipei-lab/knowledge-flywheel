#!/usr/bin/env python3
"""List pending Codex translation requests."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "content" / "codex_tasks" / "translation_requests"


def status_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Show completed requests too.")
    args = parser.parse_args()

    requests = sorted(REQUESTS.glob("*.md")) if REQUESTS.exists() else []
    visible = []
    for path in requests:
        status = status_of(path)
        if args.all or status == "pending":
            visible.append((path, status))

    if not visible:
        print("No pending Codex translation requests.")
        return 0

    for index, (path, status) in enumerate(visible, 1):
        print(f"{index}. [{status}] {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
