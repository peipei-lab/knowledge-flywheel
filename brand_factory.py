#!/usr/bin/env python3
"""Unified console for Creator's personal brand knowledge factory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"


def run_step(args: list[str]) -> int:
    print("\n$ " + " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT).returncode


def py(script_name: str, *args: str) -> list[str]:
    return [sys.executable, str(SCRIPTS / script_name), *[str(arg) for arg in args if arg is not None]]


def optional(flag: str, value: object | None) -> list[str]:
    return [flag, str(value)] if value not in (None, "") else []


def add_no_ai(args: list[str], no_ai: bool) -> list[str]:
    return [*args, "--no-ai"] if no_ai else args


def sync_all_vaults() -> int:
    print("\n同步 Obsidian vault...", flush=True)
    for cmd in [
        py("sync_obsidian.py"),
        py("sync_capture_vaults.py"),
        py("sync_book_vault.py"),
    ]:
        code = run_step(cmd)
        if code:
            return code
    return 0


def run_with_auto_sync(args: list[str], enabled: bool = True) -> int:
    code = run_step(args)
    if code or not enabled:
        return code
    return sync_all_vaults()


def command_weekly(args: argparse.Namespace) -> int:
    cmd = ["bash", str(SCRIPTS / "weekly_run.sh")]
    if args.date:
        cmd.append(args.date)
    return run_with_auto_sync(cmd, not args.no_sync)


def command_huaren_search(args: argparse.Namespace) -> int:
    cmd = py(
        "search_huaren.py",
        *optional("--keywords", args.keywords),
        *optional("--prompt", args.prompt),
        *optional("--date", args.date),
        *optional("--pages", args.pages),
        *optional("--max-results", args.max_results),
        *optional("--model", args.model),
    )
    return run_with_auto_sync(add_no_ai(cmd, args.no_ai), not args.no_sync)


def latest_huaren_manifest() -> Path | None:
    huaren_dir = ROOT / "content" / "community" / "huaren"
    manifests = sorted(huaren_dir.glob("*-manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return manifests[0] if manifests else None


def load_huaren_results(manifest_path: Path) -> list[dict[str, object]]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    results = data.get("results", [])
    return results if isinstance(results, list) else []


def parse_selection(value: str, max_index: int) -> list[int]:
    selected: list[int] = []
    for part in value.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = [piece.strip() for piece in part.split("-", 1)]
            if not start_text.isdigit() or not end_text.isdigit():
                return []
            start, end = int(start_text), int(end_text)
            if start > end:
                start, end = end, start
            selected.extend(range(start, end + 1))
        elif part.isdigit():
            selected.append(int(part))
        else:
            return []
    deduped: list[int] = []
    for index in selected:
        if index < 1 or index > max_index or index in deduped:
            continue
        deduped.append(index)
    return deduped


def fetch_huaren_threads_by_indexes(args: argparse.Namespace, results: list[dict[str, object]], indexes: list[int]) -> int:
    if not indexes:
        print("没有有效编号，已停止。")
        return 1

    for index in indexes:
        selected = results[index - 1]
        url = str(selected.get("url", "")).strip()
        if not url:
            print(f"跳过候选 {index}：没有 URL。")
            continue
        print(f"\n抓取候选 {index}: {selected.get('title', '')}")
        thread_args = argparse.Namespace(
            url=url,
            date=args.date,
            pages=args.thread_pages,
            excerpt_chars=None,
            model=args.model,
            no_ai=args.no_ai,
            no_sync=True,
        )
        code = command_huaren_thread(thread_args)
        if code:
            return code

    return 0 if args.no_sync else sync_all_vaults()


def command_huaren_guided(args: argparse.Namespace) -> int:
    original_no_sync = args.no_sync
    args.no_sync = True
    search_code = command_huaren_search(args)
    args.no_sync = original_no_sync
    if search_code:
        return search_code

    manifest_path = latest_huaren_manifest()
    if not manifest_path:
        print("没有找到 Huaren 搜索结果 manifest。")
        return 1

    results = load_huaren_results(manifest_path)
    if not results:
        print("没有搜索到候选帖子。可以换一组关键词或提示词再试。")
        return 0

    print("\n候选帖子：")
    for index, item in enumerate(results[: args.show], 1):
        print(f"{index}. {item.get('title', '')}")
        print(f"   Score: {item.get('score', '')}")
        print(f"   {item.get('url', '')}")

    shown_count = min(len(results), args.show)
    if args.auto_fetch_top:
        indexes = list(range(1, min(args.auto_fetch_top, shown_count) + 1))
        print(f"\n自动按 ranking 抓取前 {len(indexes)} 个候选。")
        return fetch_huaren_threads_by_indexes(args, results, indexes)

    selection = ask("输入编号如 2,3,4,10 或 1-5；直接回车则自动抓 top 10", "")
    if not selection:
        indexes = list(range(1, min(args.default_top, shown_count) + 1))
    else:
        indexes = parse_selection(selection, shown_count)
    return fetch_huaren_threads_by_indexes(args, results, indexes)


def command_huaren_thread(args: argparse.Namespace) -> int:
    cmd = py(
        "fetch_huaren_thread.py",
        args.url,
        *optional("--date", args.date),
        *optional("--pages", args.pages),
        *optional("--excerpt-chars", args.excerpt_chars),
        *optional("--model", args.model),
    )
    return run_with_auto_sync(add_no_ai(cmd, args.no_ai), not args.no_sync)


def command_xhs_brief(args: argparse.Namespace) -> int:
    cmd = py(
        "xiaohongshu_research_brief.py",
        *optional("--keywords", args.keywords),
        *optional("--prompt", args.prompt),
        *optional("--date", args.date),
    )
    return run_with_auto_sync(cmd, not args.no_sync)


def command_xhs_import(args: argparse.Namespace) -> int:
    return run_with_auto_sync(
        py("import_xiaohongshu.py", args.input_file, *optional("--date", args.date)),
        not args.no_sync,
    )


def command_ebook_search(args: argparse.Namespace) -> int:
    cmd = py(
        "search_public_ebooks.py",
        "--query",
        args.query,
        *optional("--date", args.date),
        *optional("--limit", args.limit),
        *optional("--download-id", args.download_id),
        *optional("--prefer", args.prefer),
    )
    return run_with_auto_sync(cmd, not args.no_sync)


def command_ebook_analyze(args: argparse.Namespace) -> int:
    cmd = py(
        "analyze_ebook.py",
        args.book_file,
        *optional("--title", args.title),
        *optional("--max-chapters", args.max_chapters),
        *optional("--min-chars", args.min_chars),
        *optional("--chapter-chars", args.chapter_chars),
        *optional("--model", args.model),
    )
    return run_with_auto_sync(add_no_ai(cmd, args.no_ai), not args.no_sync)


def command_sync(_: argparse.Namespace) -> int:
    return sync_all_vaults()


def command_monitor(args: argparse.Namespace) -> int:
    cmd = py("monitor_capture_vault.py", *optional("--interval", args.interval))
    if args.once:
        cmd.append("--once")
    return run_with_auto_sync(add_no_ai(cmd, args.no_ai), args.once and not args.no_sync)


def command_notebooklm(args: argparse.Namespace) -> int:
    cmd = py(
        "notebooklm_adapter.py",
        *optional("--notebook-id", args.notebook_id),
        *optional("--create-title", args.create_title),
        *optional("--prompt-file", args.prompt_file),
        *optional("--output-name", args.output_name),
    )
    for source in args.source or []:
        cmd.extend(["--source", source])
    if args.skip_auth_check:
        cmd.append("--skip-auth-check")
    return run_with_auto_sync(cmd, not args.no_sync)


def command_review_build(args: argparse.Namespace) -> int:
    cmd = py("build_review_inbox.py", *optional("--limit", args.limit))
    if args.include_reviewed:
        cmd.append("--include-reviewed")
    return run_with_auto_sync(cmd, not args.no_sync)


def command_review_ui(args: argparse.Namespace) -> int:
    return run_step(py("review_server.py", "--host", args.host, "--port", args.port))


def command_review_feedback(args: argparse.Namespace) -> int:
    cmd = py(
        "record_feedback.py",
        "--item-id",
        args.item_id,
        "--decision",
        args.decision,
        "--relevance",
        args.relevance,
        "--insight",
        args.insight,
        "--voice-match",
        args.voice_match,
        "--publishability",
        args.publishability,
        "--life-reflection-value",
        args.life_reflection_value,
        *optional("--feedback-type", args.feedback_type),
        *optional("--item-type", args.item_type),
        *optional("--source-path", args.source_path),
        *optional("--source-url", args.source_url),
        *optional("--tags", args.tags),
        *optional("--feedback-text", args.feedback_text),
        *optional("--rewrite-instruction", args.rewrite_instruction),
        *optional("--voice-axis", args.voice_axis),
    )
    if args.memory_candidate:
        cmd.append("--memory-candidate")
    return run_with_auto_sync(cmd, not args.no_sync)


def command_memory_reflect(args: argparse.Namespace) -> int:
    cmd = py(
        "promote_principles.py",
        *optional("--date", args.date),
        *optional("--limit", args.limit),
    )
    return run_with_auto_sync(cmd, not args.no_sync)


def command_memory_init_identity(args: argparse.Namespace) -> int:
    cmd = py("init_identity.py")
    if args.overwrite:
        cmd.append("--overwrite")
    return run_with_auto_sync(cmd, not args.no_sync)


def command_pages_draft(args: argparse.Namespace) -> int:
    cmd = py(
        "generate_pages_article.py",
        "--candidate-id",
        args.candidate_id,
        *optional("--slug", args.slug),
        *optional("--title", args.title),
        *optional("--date", args.date),
        *optional("--model", args.model),
    )
    if args.no_ai:
        cmd.append("--no-ai")
    return run_with_auto_sync(cmd, not args.no_sync)


def command_pages_publish(args: argparse.Namespace) -> int:
    cmd = py(
        "publish_pages_article.py",
        "--slug",
        args.slug,
        *optional("--repo-path", args.repo_path),
        *optional("--posts-dir", args.posts_dir),
    )
    if args.dry_run:
        cmd.append("--dry-run")
    if args.stage_only:
        cmd.append("--stage-only")
    if args.git_commit:
        cmd.append("--git-commit")
    if args.git_push:
        cmd.append("--git-push")
    if args.message:
        cmd.extend(["--message", args.message])
    return run_with_auto_sync(cmd, not args.no_sync)


def command_pages_translation_queue(args: argparse.Namespace) -> int:
    cmd = py("list_translation_requests.py")
    if args.all:
        cmd.append("--all")
    return run_step(cmd)


def command_smoke_test(args: argparse.Namespace) -> int:
    cmd = py(
        "smoke_test.py",
        *optional("--slug", args.slug),
        *optional("--ui-url", args.ui_url),
    )
    if args.skip_ui:
        cmd.append("--skip-ui")
    if args.require_ui:
        cmd.append("--require-ui")
    if args.skip_sync:
        cmd.append("--skip-sync")
    return run_step(cmd)


def command_intake_test(args: argparse.Namespace) -> int:
    prompt = args.prompt or "AI 时代妈妈如何训练孩子的判断力，而不是只堆工具和课程"
    keywords = args.keywords or "AI,孩子,教育,妈妈,学习"
    code = 0

    print("\nIntake test topic:")
    print(f"- Prompt: {prompt}")
    print(f"- Keywords: {keywords}")

    steps: list[list[str]] = [
        py(
            "xiaohongshu_research_brief.py",
            "--prompt",
            prompt,
            "--keywords",
            keywords,
            *optional("--date", args.date),
        )
    ]

    if not args.skip_huaren:
        huaren_cmd = [
            *py(
                "search_huaren.py",
                "--prompt",
                prompt,
                "--keywords",
                keywords,
                "--pages",
                str(args.pages),
                "--max-results",
                str(args.max_results),
                *optional("--date", args.date),
            ),
            "--no-ai",
        ]
        steps.append(huaren_cmd)

    for step in steps:
        code = run_step(step)
        if code:
            return code

    if args.fetch_top and not args.skip_huaren:
        guided_args = argparse.Namespace(
            keywords=keywords,
            prompt=prompt,
            date=args.date,
            pages=args.pages,
            max_results=args.max_results,
            show=max(args.fetch_top, args.max_results),
            default_top=args.fetch_top,
            auto_fetch_top=args.fetch_top,
            thread_pages=args.thread_pages,
            model=None,
            no_ai=True,
            no_sync=True,
        )
        code = command_huaren_guided(guided_args)
        if code:
            return code

    if not args.skip_monitor:
        code = sync_all_vaults()
        if code:
            return code
        code = run_step(py("monitor_capture_vault.py", "--once", "--no-ai"))
        if code:
            return code
        code = run_step(py("build_review_inbox.py", "--limit", str(args.review_limit)))
        if code:
            return code

    if args.no_sync:
        return 0
    return sync_all_vaults()


def command_paths(_: argparse.Namespace) -> int:
    paths = {
        "项目根目录": ROOT,
        "原始抓取 vault": ROOT / "raw_capture_vault",
        "分析结果 vault": ROOT / "insight_vault",
        "电子书 vault": ROOT / "book_vault",
        "综合 vault": ROOT / "obsidian_vault",
        "内容输出": ROOT / "content",
        "Pages 草稿": ROOT / "content" / "pages_drafts",
        "Pages 发布配置": ROOT / "config" / "github_pages.json",
    }
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def interactive() -> int:
    while True:
        print(
            """
Creator Brand Factory

1. 运行每周 AI 信息源周报
2. 按关键词/prompt 搜索 Huaren
3. 搜索 Huaren 候选，并自动/多选抓取评论
30. 维护：输入 Huaren URL 精确抓取帖子和评论
4. 生成小红书人工研究清单
5. 导入小红书帖子/评论文件
6. 搜索公共版权电子书
7. 分析电子书章节
8. 扫描一次 raw_capture_vault 并生成分析
9. 调用可选 NotebookLM adapter
10. 查看路径
11. 构建 HITL Review Inbox
12. 启动本地 HITL Review UI
13. 手动记录一条 Creator feedback
14. 从 Review candidate 生成 GitHub Pages 双语草稿
15. 发布双语草稿到 GitHub Pages repo
16. 查看 Codex translation queue
17. 运行本地 smoke test
18. 运行 intake/search test
90. 维护：手动重新同步所有 Obsidian vault
91. 维护：启动本地前台持续监控
0. 退出
""".strip()
        )
        choice = ask("选择功能")
        if choice == "0":
            return 0
        if choice == "1":
            return main(["weekly", *optional("--date", ask("日期 YYYY-MM-DD，可留空"))])
        if choice == "2":
            keywords = ask("关键词，用逗号分隔，可留空")
            prompt = ask("自然语言搜索意图，可留空")
            return main(["huaren", "search", *optional("--keywords", keywords), *optional("--prompt", prompt), "--no-ai"])
        if choice == "3":
            keywords = ask("关键词，用逗号分隔，可留空")
            prompt = ask("自然语言搜索意图，可留空")
            top_n = ask("自动抓取 ranking 前几个候选；输入 0 则只保存候选列表", "10")
            argv = ["huaren", "guided", *optional("--keywords", keywords), *optional("--prompt", prompt), "--no-ai"]
            if top_n != "0":
                argv.extend(["--auto-fetch-top", top_n])
            return main(argv)
        if choice == "30":
            return main(["huaren", "thread", ask("Huaren 帖子 URL"), "--pages", ask("抓取页数", "1"), "--no-ai"])
        if choice == "4":
            keywords = ask("小红书关键词，可留空")
            prompt = ask("研究意图，可留空")
            return main(["xhs", "brief", *optional("--keywords", keywords), *optional("--prompt", prompt)])
        if choice == "5":
            return main(["xhs", "import", ask("JSON/CSV/Markdown/TXT 文件路径")])
        if choice == "6":
            return main(["ebook", "search", "--query", ask("搜索主题/关键词"), "--limit", ask("结果数量", "10")])
        if choice == "7":
            return main(["ebook", "analyze", ask("电子书 txt/epub 文件路径"), "--max-chapters", ask("最多章节数", "8"), "--no-ai"])
        if choice == "8":
            return main(["monitor", "--once", "--no-ai"])
        if choice == "9":
            title = ask("Notebook 标题，可留空")
            source = ask("source 文件或 URL，可留空")
            prompt_file = ask("prompt 文件", "prompts/book_chapter_analysis.md")
            argv = ["notebooklm", *optional("--create-title", title), *optional("--prompt-file", prompt_file)]
            if source:
                argv.extend(["--source", source])
            return main(argv)
        if choice == "10":
            return main(["paths"])
        if choice == "11":
            return main(["review", "build", "--limit", ask("候选数量", "20")])
        if choice == "12":
            return main(["review", "ui", "--port", ask("本地端口", "8765")])
        if choice == "13":
            return main(
                [
                    "review",
                    "feedback",
                    "--item-id",
                    ask("Candidate ID / Item ID"),
                    "--decision",
                    ask("Decision: keep/skip/rewrite/publish/deepen/archive", "keep"),
                    "--feedback-text",
                    ask("Raw feedback"),
                ]
            )
        if choice == "14":
            argv = [
                "pages",
                "draft",
                "--candidate-id",
                ask("Candidate ID"),
                "--slug",
                ask("文章 slug，可留空"),
            ]
            if ask("没有 OPENAI_API_KEY 时生成结构草稿？yes/no", "yes").lower().startswith("y"):
                argv.append("--no-ai")
            return main(argv)
        if choice == "15":
            slug = ask("文章 slug")
            repo = ask("GitHub Pages 本地 repo 路径；留空使用 config/github_pages.json")
            argv = ["pages", "publish", "--slug", slug, *optional("--repo-path", repo)]
            if ask("只发布到本地 staging 目录测试？yes/no", "yes").lower().startswith("y"):
                argv.append("--stage-only")
            return main(argv)
        if choice == "16":
            return main(["pages", "translation-queue"])
        if choice == "17":
            return main(["smoke-test"])
        if choice == "18":
            prompt = ask("研究 prompt", "AI 时代妈妈如何训练孩子的判断力，而不是只堆工具和课程")
            keywords = ask("关键词", "AI,孩子,教育,妈妈,学习")
            fetch_top = ask("抓取 Huaren top N 帖评论；0 表示只搜索不抓评论", "0")
            return main(["intake-test", "--prompt", prompt, "--keywords", keywords, "--fetch-top", fetch_top])
        if choice == "90":
            return main(["sync"])
        if choice == "91":
            return main(["monitor", "--interval", ask("扫描间隔秒数", "300"), "--no-ai"])
        print("没有这个选项，请重新选择。\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for Creator Brand Factory.")
    sub = parser.add_subparsers(dest="command")

    weekly = sub.add_parser("weekly", help="Run weekly curated-source pipeline.")
    weekly.add_argument("--date")
    weekly.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    weekly.set_defaults(func=command_weekly)

    huaren = sub.add_parser("huaren", help="Huaren search and thread/comment capture.")
    huaren_sub = huaren.add_subparsers(dest="huaren_command", required=True)

    hs = huaren_sub.add_parser("search", help="Search Huaren by keywords or natural-language prompt.")
    hs.add_argument("--keywords")
    hs.add_argument("--prompt")
    hs.add_argument("--date")
    hs.add_argument("--pages", type=int)
    hs.add_argument("--max-results", type=int)
    hs.add_argument("--model")
    hs.add_argument("--no-ai", action="store_true")
    hs.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    hs.set_defaults(func=command_huaren_search)

    hg = huaren_sub.add_parser("guided", help="Search Huaren, show candidates, then optionally fetch one thread.")
    hg.add_argument("--keywords")
    hg.add_argument("--prompt")
    hg.add_argument("--date")
    hg.add_argument("--pages", type=int)
    hg.add_argument("--max-results", type=int)
    hg.add_argument("--show", type=int, default=10, help="Number of candidates to show for selection.")
    hg.add_argument("--default-top", type=int, default=10, help="How many top-ranked candidates to fetch when pressing Enter.")
    hg.add_argument("--auto-fetch-top", type=int, default=0, help="Fetch top N ranked candidates without asking for selection.")
    hg.add_argument("--thread-pages", type=int, default=1, help="Comment pages to fetch after selecting a candidate.")
    hg.add_argument("--model")
    hg.add_argument("--no-ai", action="store_true")
    hg.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    hg.set_defaults(func=command_huaren_guided)

    ht = huaren_sub.add_parser("thread", help="Fetch a public Huaren thread with comments.")
    ht.add_argument("url")
    ht.add_argument("--date")
    ht.add_argument("--pages", type=int)
    ht.add_argument("--excerpt-chars", type=int)
    ht.add_argument("--model")
    ht.add_argument("--no-ai", action="store_true")
    ht.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    ht.set_defaults(func=command_huaren_thread)

    xhs = sub.add_parser("xhs", help="Xiaohongshu manual research/import workflow.")
    xhs_sub = xhs.add_subparsers(dest="xhs_command", required=True)

    xb = xhs_sub.add_parser("brief", help="Create prompt-driven manual Xiaohongshu research brief.")
    xb.add_argument("--keywords")
    xb.add_argument("--prompt")
    xb.add_argument("--date")
    xb.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    xb.set_defaults(func=command_xhs_brief)

    xi = xhs_sub.add_parser("import", help="Import manually saved/exported Xiaohongshu posts/comments.")
    xi.add_argument("input_file")
    xi.add_argument("--date")
    xi.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    xi.set_defaults(func=command_xhs_import)

    ebook = sub.add_parser("ebook", help="Public ebook search and chapter analysis.")
    ebook_sub = ebook.add_subparsers(dest="ebook_command", required=True)

    es = ebook_sub.add_parser("search", help="Search/download public-domain ebooks.")
    es.add_argument("--query", required=True)
    es.add_argument("--date")
    es.add_argument("--limit", type=int)
    es.add_argument("--download-id")
    es.add_argument("--prefer", choices=["txt", "epub"])
    es.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    es.set_defaults(func=command_ebook_search)

    ea = ebook_sub.add_parser("analyze", help="Analyze txt/epub chapters into knowledge atoms.")
    ea.add_argument("book_file")
    ea.add_argument("--title")
    ea.add_argument("--max-chapters", type=int)
    ea.add_argument("--min-chars", type=int)
    ea.add_argument("--chapter-chars", type=int)
    ea.add_argument("--model")
    ea.add_argument("--no-ai", action="store_true")
    ea.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    ea.set_defaults(func=command_ebook_analyze)

    sync = sub.add_parser("sync", help="Sync all Obsidian-compatible vaults.")
    sync.set_defaults(func=command_sync)

    monitor = sub.add_parser("monitor", help="Monitor raw_capture_vault and generate analyses.")
    monitor.add_argument("--interval", type=int)
    monitor.add_argument("--once", action="store_true")
    monitor.add_argument("--no-ai", action="store_true")
    monitor.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after a one-shot scan.")
    monitor.set_defaults(func=command_monitor)

    nb = sub.add_parser("notebooklm", help="Optional wrapper for unofficial notebooklm-py CLI.")
    nb.add_argument("--notebook-id")
    nb.add_argument("--create-title")
    nb.add_argument("--source", action="append")
    nb.add_argument("--prompt-file")
    nb.add_argument("--output-name")
    nb.add_argument("--skip-auth-check", action="store_true")
    nb.add_argument("--no-sync", action="store_true", help="Skip automatic Obsidian vault sync after success.")
    nb.set_defaults(func=command_notebooklm)

    review = sub.add_parser("review", help="HITL review inbox, UI, and feedback tools.")
    review_sub = review.add_subparsers(dest="review_command", required=True)

    rb = review_sub.add_parser("build", help="Build Review Inbox candidates from insight analyses.")
    rb.add_argument("--limit", type=int, default=20)
    rb.add_argument("--include-reviewed", action="store_true")
    rb.add_argument("--no-sync", action="store_true")
    rb.set_defaults(func=command_review_build)

    rui = review_sub.add_parser("ui", help="Start local browser-based Review UI.")
    rui.add_argument("--host", default="127.0.0.1")
    rui.add_argument("--port", type=int, default=8765)
    rui.set_defaults(func=command_review_ui)

    rf = review_sub.add_parser("feedback", help="Append one immutable raw feedback event.")
    rf.add_argument("--item-id", required=True)
    rf.add_argument("--decision", required=True, choices=["keep", "skip", "rewrite", "publish", "deepen", "archive"])
    rf.add_argument("--feedback-type", default="quick_review")
    rf.add_argument("--item-type", default="analysis")
    rf.add_argument("--source-path", default="")
    rf.add_argument("--source-url", default="")
    rf.add_argument("--relevance", type=int, default=3)
    rf.add_argument("--insight", type=int, default=3)
    rf.add_argument("--voice-match", type=int, default=3)
    rf.add_argument("--publishability", type=int, default=3)
    rf.add_argument("--life-reflection-value", type=int, default=3)
    rf.add_argument("--tags", default="")
    rf.add_argument("--feedback-text", default="")
    rf.add_argument("--rewrite-instruction", default="")
    rf.add_argument("--voice-axis", default="mixed")
    rf.add_argument("--memory-candidate", action="store_true")
    rf.add_argument("--no-sync", action="store_true")
    rf.set_defaults(func=command_review_feedback)

    memory = sub.add_parser("memory", help="Promote feedback into preference principles.")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)

    mr = memory_sub.add_parser("reflect", help="Distill raw feedback and curated choices into principles.")
    mr.add_argument("--date")
    mr.add_argument("--limit", type=int, default=80)
    mr.add_argument("--no-sync", action="store_true")
    mr.set_defaults(func=command_memory_reflect)

    mi = memory_sub.add_parser("init-identity", help="Create local identity files from public templates.")
    mi.add_argument("--overwrite", action="store_true")
    mi.add_argument("--no-sync", action="store_true")
    mi.set_defaults(func=command_memory_init_identity)

    pages = sub.add_parser("pages", help="Generate and publish bilingual GitHub Pages articles.")
    pages_sub = pages.add_subparsers(dest="pages_command", required=True)

    pd = pages_sub.add_parser("draft", help="Generate bilingual Pages drafts from a reviewed candidate.")
    pd.add_argument("--candidate-id", required=True)
    pd.add_argument("--slug")
    pd.add_argument("--title")
    pd.add_argument("--date")
    pd.add_argument("--model")
    pd.add_argument("--no-ai", action="store_true")
    pd.add_argument("--no-sync", action="store_true")
    pd.set_defaults(func=command_pages_draft)

    pp = pages_sub.add_parser("publish", help="Copy bilingual Pages drafts into a GitHub Pages repo.")
    pp.add_argument("--slug", required=True)
    pp.add_argument("--repo-path")
    pp.add_argument("--posts-dir")
    pp.add_argument("--dry-run", action="store_true")
    pp.add_argument("--stage-only", action="store_true", help="Publish to local content/pages_published for testing.")
    pp.add_argument("--git-commit", action="store_true")
    pp.add_argument("--git-push", action="store_true")
    pp.add_argument("--message")
    pp.add_argument("--no-sync", action="store_true")
    pp.set_defaults(func=command_pages_publish)

    tq = pages_sub.add_parser("translation-queue", help="List pending Codex translation requests.")
    tq.add_argument("--all", action="store_true")
    tq.set_defaults(func=command_pages_translation_queue)

    paths = sub.add_parser("paths", help="Show project and vault paths.")
    paths.set_defaults(func=command_paths)

    smoke = sub.add_parser("smoke-test", help="Run local end-to-end smoke test.")
    smoke.add_argument("--slug", default="smoke-test-auto")
    smoke.add_argument("--ui-url", default="http://127.0.0.1:8765")
    smoke.add_argument("--skip-ui", action="store_true")
    smoke.add_argument("--require-ui", action="store_true")
    smoke.add_argument("--skip-sync", action="store_true")
    smoke.set_defaults(func=command_smoke_test)

    intake = sub.add_parser("intake-test", help="Run prompt/keyword-driven intake search test.")
    intake.add_argument("--prompt", default="")
    intake.add_argument("--keywords", default="")
    intake.add_argument("--date")
    intake.add_argument("--pages", type=int, default=1)
    intake.add_argument("--max-results", type=int, default=10)
    intake.add_argument("--fetch-top", type=int, default=0, help="Fetch top N Huaren threads/comments after searching.")
    intake.add_argument("--thread-pages", type=int, default=1)
    intake.add_argument("--review-limit", type=int, default=20)
    intake.add_argument("--skip-huaren", action="store_true", help="Only generate local Xiaohongshu research brief.")
    intake.add_argument("--skip-monitor", action="store_true", help="Skip capture monitor and review inbox rebuild.")
    intake.add_argument("--no-sync", action="store_true")
    intake.set_defaults(func=command_intake_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return interactive()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
