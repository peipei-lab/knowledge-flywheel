#!/usr/bin/env python3
"""Publish bilingual article drafts into a local GitHub Pages repository."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "github_pages.json"
DRAFTS = ROOT / "content" / "pages_drafts"
PUBLISHED = ROOT / "content" / "pages_published"


def load_config() -> dict[str, object]:
    if not CONFIG.exists():
        return {}
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def latest_pair(slug: str) -> tuple[Path, Path]:
    article_dir = DRAFTS / slug
    zh = sorted(article_dir.glob("*.zh.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    en = sorted(article_dir.glob("*.en.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not zh or not en:
        raise SystemExit(f"Missing bilingual drafts under {article_dir}")
    return zh[0], en[0]


def publish_to(target_dir: Path, zh_path: Path, en_path: Path, dry_run: bool) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs = [target_dir / zh_path.name, target_dir / en_path.name]
    if not dry_run:
        shutil.copyfile(zh_path, outputs[0])
        shutil.copyfile(en_path, outputs[1])
    return outputs


def git_commit(repo: Path, files: list[Path], message: str, push: bool, dry_run: bool) -> None:
    rel_files = [str(path.relative_to(repo)) for path in files]
    commands = [
        ["git", "add", *rel_files],
        ["git", "commit", "-m", message],
    ]
    if push:
        commands.append(["git", "push"])
    for cmd in commands:
        if dry_run:
            print("$ " + " ".join(cmd))
            continue
        result = subprocess.run(cmd, cwd=repo)
        if result.returncode:
            raise SystemExit(f"Git command failed: {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--repo-path", help="Local GitHub Pages repository path. Overrides config/github_pages.json.")
    parser.add_argument("--posts-dir", help="Posts directory inside repo. Defaults to config value or _posts.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stage-only", action="store_true", help="Copy to local content/pages_published instead of a GitHub repo.")
    parser.add_argument("--git-commit", action="store_true", help="Commit published files in the GitHub Pages repo.")
    parser.add_argument("--git-push", action="store_true", help="Push after committing. Requires network/auth.")
    parser.add_argument("--message", default="")
    args = parser.parse_args()

    config = load_config()
    zh_path, en_path = latest_pair(args.slug)
    posts_dir = args.posts_dir or str(config.get("posts_dir") or "_posts")
    repo = None

    if args.stage_only:
        target = PUBLISHED / posts_dir
    else:
        repo_path = args.repo_path or str(config.get("repo_path") or "")
        if not repo_path:
            raise SystemExit(
                "GitHub Pages repo path is not configured. Set config/github_pages.json repo_path, "
                "or rerun with --repo-path /path/to/your/pages/repo. Use --stage-only to test locally."
            )
        repo = Path(repo_path).expanduser()
        target = repo / posts_dir

    outputs = publish_to(target, zh_path, en_path, args.dry_run)
    should_commit = bool(args.git_commit or config.get("commit_after_publish"))
    should_push = bool(args.git_push or config.get("push_after_publish"))
    if should_push:
        should_commit = True
    if should_commit:
        if args.stage_only or repo is None:
            raise SystemExit("Git commit/push is only available when publishing to a real GitHub Pages repo.")
        message = args.message or f"Publish bilingual article: {args.slug}"
        git_commit(repo, outputs, message, should_push, args.dry_run)

    marker = "Would publish" if args.dry_run else "Published"
    print(f"{marker} bilingual Pages article at {datetime.now().isoformat(timespec='seconds')}:")
    for path in outputs:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
