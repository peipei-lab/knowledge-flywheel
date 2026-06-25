#!/usr/bin/env python3
"""Run a local end-to-end smoke test for Knowledge Flywheel."""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INBOX = ROOT / "insight_vault" / "60_Review_Inbox" / "candidates.jsonl"
PYCACHE = ROOT / "work" / "pycache"


class Smoke:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, label: str) -> None:
        print(f"PASS {label}")

    def fail(self, label: str, detail: str = "") -> None:
        message = f"FAIL {label}" + (f": {detail}" if detail else "")
        self.failures.append(message)
        print(message)

    def warn(self, label: str, detail: str = "") -> None:
        message = f"WARN {label}" + (f": {detail}" if detail else "")
        print(message)

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.pass_(label)
        else:
            self.fail(label, detail)

    def run_cmd(self, label: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
        if result.returncode == 0:
            self.pass_(label)
        else:
            self.fail(label, (result.stderr or result.stdout).strip())
        return result


def py(script: str, *args: str) -> list[str]:
    return [sys.executable, str(SCRIPTS / script), *args]


def compile_python(smoke: Smoke) -> None:
    PYCACHE.mkdir(parents=True, exist_ok=True)
    sys.pycache_prefix = str(PYCACHE)
    files = [ROOT / "brand_factory.py", *sorted(SCRIPTS.glob("*.py"))]
    try:
        for path in files:
            py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        smoke.fail("Python compile", str(exc))
        return
    smoke.pass_("Python compile")


def load_candidate_id() -> str:
    if not INBOX.exists():
        return ""
    for line in INBOX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate_id = str(item.get("candidate_id") or "")
        if candidate_id:
            return candidate_id
    return ""


def check_review_ui(smoke: Smoke, url: str, require_ui: bool) -> None:
    try:
        materials = urllib.request.urlopen(f"{url}/?track=materials", timeout=3).read().decode("utf-8")
        drafts = urllib.request.urlopen(f"{url}/?track=drafts", timeout=3).read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        if require_ui:
            smoke.fail("Review UI reachable", str(exc))
        else:
            smoke.warn("Review UI reachable", str(exc))
        return
    smoke.pass_("Review UI reachable")
    smoke.check("Materials tab", "material_review" in materials)
    smoke.check("Drafts tab", "draft_review" in drafts)
    smoke.check("Draft translation status", "English:" in drafts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="smoke-test-auto")
    parser.add_argument("--ui-url", default="http://127.0.0.1:8765")
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument("--require-ui", action="store_true", help="Fail if the local Review UI cannot be reached.")
    parser.add_argument("--skip-sync", action="store_true")
    args = parser.parse_args()

    smoke = Smoke()
    os.environ.setdefault("PYTHONPYCACHEPREFIX", str(PYCACHE))
    compile_python(smoke)

    smoke.run_cmd("Review inbox build", [*py("build_review_inbox.py"), "--limit", "20"])
    candidate_id = load_candidate_id()
    smoke.check("Candidate available", bool(candidate_id), "No candidate_id in Review Inbox")

    if candidate_id:
        smoke.run_cmd(
            "Pages draft generation",
            [*py("generate_pages_article.py"), "--candidate-id", candidate_id, "--slug", args.slug, "--no-ai"],
        )
        zh = ROOT / "content" / "pages_drafts" / args.slug / f"2026-06-24-{args.slug}.zh.md"
        en = ROOT / "content" / "pages_drafts" / args.slug / f"2026-06-24-{args.slug}.en.md"
        request = ROOT / "content" / "codex_tasks" / "translation_requests" / f"{args.slug}-translation-request.md"
        smoke.check("Chinese draft exists", zh.exists())
        smoke.check("English draft exists", en.exists())
        smoke.check("Translation request exists", request.exists())
        if en.exists():
            smoke.check("English draft is pending", "English translation pending" in en.read_text(encoding="utf-8"))

        smoke.run_cmd("Translation queue list", [*py("list_translation_requests.py")])
        smoke.run_cmd("Staging publish", [*py("publish_pages_article.py"), "--slug", args.slug, "--stage-only"])
        published = ROOT / "content" / "pages_published" / "_posts" / f"2026-06-24-{args.slug}.en.md"
        smoke.check("Staged English post exists", published.exists())

    if not args.skip_sync:
        smoke.run_cmd("Obsidian sync", [*py("sync_obsidian.py")])

    if not args.skip_ui:
        check_review_ui(smoke, args.ui_url.rstrip("/"), args.require_ui)

    if smoke.failures:
        print("\nSmoke test failed:")
        for failure in smoke.failures:
            print(f"- {failure}")
        return 1

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
