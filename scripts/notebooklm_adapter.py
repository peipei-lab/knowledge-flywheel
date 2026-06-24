#!/usr/bin/env python3
"""Optional adapter for the unofficial notebooklm-py CLI.

This script does not install notebooklm-py and does not depend on it by default.
If the user has installed and authenticated the `notebooklm` CLI, this adapter
can create/use a notebook, add local ebook/chapter sources, ask an analysis
prompt, and save the output into the local Obsidian book vault.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOK_VAULT = ROOT / "book_vault"
NOTEBOOKLM_OUT = BOOK_VAULT / "50_NotebookLM_Outputs"
DEFAULT_PROMPT = ROOT / "prompts" / "book_chapter_analysis.md"
LOCAL_NOTEBOOKLM = ROOT / ".venv" / "bin" / "notebooklm"


def notebooklm_bin() -> str:
    if LOCAL_NOTEBOOKLM.exists():
        return str(LOCAL_NOTEBOOKLM)
    found = shutil.which("notebooklm")
    if found:
        return found
    raise SystemExit(
        "The `notebooklm` CLI was not found. Install and authenticate notebooklm-py first, "
        "then rerun this adapter."
    )


def run_notebooklm(args: list[str]) -> str:
    result = subprocess.run([notebooklm_bin(), *args], check=True, text=True, capture_output=True)
    return result.stdout.strip()


def slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in value).strip().lower()
    return "-".join(safe.split())[:80] or "notebooklm-output"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook-id", help="Existing NotebookLM notebook id.")
    parser.add_argument("--create-title", help="Create a new NotebookLM notebook with this title.")
    parser.add_argument("--source", action="append", default=[], help="Local file path or URL source to add. Repeatable.")
    parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT), help="Prompt file to ask against the notebook.")
    parser.add_argument("--output-name", default="", help="Output Markdown file stem.")
    parser.add_argument("--skip-auth-check", action="store_true")
    args = parser.parse_args()

    if not args.skip_auth_check:
        run_notebooklm(["auth", "check", "--test"])

    notebook_id = args.notebook_id
    if args.create_title:
        create_output = run_notebooklm(["create", args.create_title])
        notebook_id = create_output.split()[-1] if create_output else notebook_id

    if notebook_id:
        run_notebooklm(["use", notebook_id])

    for source in args.source:
        run_notebooklm(["source", "add", source])

    prompt_path = Path(args.prompt_file).resolve()
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file does not exist: {prompt_path}")

    answer = run_notebooklm(["ask", "--prompt-file", str(prompt_path)])

    NOTEBOOKLM_OUT.mkdir(parents=True, exist_ok=True)
    stem = args.output_name or args.create_title or notebook_id or "notebooklm-analysis"
    out_path = NOTEBOOKLM_OUT / f"{slugify(stem)}-{datetime.now().date().isoformat()}.md"
    out_path.write_text(
        f"""# NotebookLM Analysis: {stem}

Generated: {datetime.now(timezone.utc).isoformat()}

Source: unofficial notebooklm-py CLI

## Boundary

This output comes from an unofficial NotebookLM client that uses undocumented Google APIs. Treat it as an optional research accelerator, not a default system dependency.

## Output

{answer}
""",
        encoding="utf-8",
    )
    print(f"Wrote NotebookLM output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
