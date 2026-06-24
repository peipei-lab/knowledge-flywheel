#!/usr/bin/env python3
"""Monitor raw_capture_vault for new files and generate analyses."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_VAULT = ROOT / "raw_capture_vault"
INSIGHT_VAULT = ROOT / "insight_vault"
STATE = ROOT / "content" / "state" / "capture_monitor_seen.json"
ANALYZE = ROOT / "scripts" / "analyze_capture_file.py"
SYNC = ROOT / "scripts" / "sync_capture_vaults.py"


WATCH_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
WATCH_DIR_NAMES = {"00_Inbox", "10_Huaren_Raw", "20_Xiaohongshu_Raw"}


def load_seen() -> set[str]:
    if not STATE.exists():
        return set()
    return set(json.loads(STATE.read_text(encoding="utf-8")))


def save_seen(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in RAW_VAULT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in WATCH_EXTENSIONS:
            continue
        if ".obsidian" in path.parts:
            continue
        if path.name.lower() in {"home.md", "knowledge map.md"}:
            continue
        if not any(part in WATCH_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def analyze(path: Path, no_ai: bool) -> None:
    output_dir = INSIGHT_VAULT / "10_Analyses"
    cmd = ["python3", str(ANALYZE), str(path), "--output-dir", str(output_dir)]
    if no_ai:
        cmd.append("--no-ai")
    subprocess.run(cmd, check=True)


def scan_once(no_ai: bool) -> int:
    subprocess.run(["python3", str(SYNC)], check=True)
    seen = load_seen()
    new_count = 0
    for path in iter_files():
        key = f"{path}:{path.stat().st_mtime_ns}"
        if key in seen:
            continue
        analyze(path, no_ai=no_ai)
        seen.add(key)
        new_count += 1
    save_seen(seen)
    subprocess.run(["python3", str(SYNC)], check=True)
    return new_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-ai", action="store_true", help="Use heuristic analysis only.")
    args = parser.parse_args()

    while True:
        count = scan_once(no_ai=args.no_ai)
        print(f"Capture monitor scanned. New files analyzed: {count}")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
