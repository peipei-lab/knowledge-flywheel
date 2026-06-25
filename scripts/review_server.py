#!/usr/bin/env python3
"""Small local HITL review UI for Creator Brand Factory."""

from __future__ import annotations

import argparse
import cgi
import html
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from profile_config import creator_name, render_profile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INBOX = ROOT / "insight_vault" / "60_Review_Inbox"
CANDIDATES_PATH = INBOX / "candidates.jsonl"
DRAFTS = ROOT / "content" / "pages_drafts"
TRANSLATION_REQUESTS = ROOT / "content" / "codex_tasks" / "translation_requests"
BOOKS_RAW = ROOT / "content" / "books" / "raw"
RAW_INBOX = ROOT / "raw_capture_vault" / "00_Inbox"


def run_brand_factory(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "brand_factory.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def safe_filename(name: str) -> str:
    base = Path(name or "uploaded-book").name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")
    return clean or "uploaded-book"


def unique_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        next_candidate = folder / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise RuntimeError("Could not create a unique upload filename.")


def source_note_filename(source_type: str, title: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = safe_filename(title or source_type).rsplit(".", 1)[0].lower()
    return f"{stamp}-curated-{source_type}-{slug}.md"


def write_curated_source_note(source_type: str, title: str, url: str, content: str, user_note: str) -> Path:
    RAW_INBOX.mkdir(parents=True, exist_ok=True)
    label = title or url or f"Curated {source_type}"
    path = unique_path(RAW_INBOX, source_note_filename(source_type, label))
    body = f"""# Curated Source: {label}

Source type: {source_type}
Source priority: curated
Curation: user_specified
Weight: high
URL: {url or "N/A"}
Captured: {datetime.now(timezone.utc).isoformat()}

## Why saved / user note

{user_note or "N/A"}

## Content

{content or "N/A"}
"""
    path.write_text(body, encoding="utf-8")
    return path


def write_curated_book_note(book_path: Path, title: str, user_note: str) -> Path:
    label = title or book_path.stem
    content = f"""Book file: {book_path.relative_to(ROOT)}

This is a user-selected local ebook. Chapter-level analysis is stored in the book vault; this curation note exists so the book itself can enter the same high-priority review workflow as other user-selected sources.
"""
    return write_curated_source_note("book", label, str(book_path.relative_to(ROOT)), content, user_note)


def write_book_curation_metadata(book_path: Path, title: str, user_note: str) -> Path:
    label = title or book_path.stem
    metadata_path = unique_path(BOOKS_RAW, f"{book_path.stem}-curation.md")
    body = f"""# Curated Book: {label}

Source type: book
Source priority: curated
Curation: user_specified
Weight: high
Book file: {book_path.name}
Captured: {datetime.now(timezone.utc).isoformat()}

## Why selected

{user_note or "N/A"}
"""
    metadata_path.write_text(body, encoding="utf-8")
    return metadata_path


def load_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in CANDIDATES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_drafts() -> list[dict[str, Any]]:
    if not DRAFTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(DRAFTS.rglob("*.zh.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        title = path.stem
        for line in text.splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
                break
            if line.startswith("# "):
                title = line.strip("# ").strip()
                break
        slug = path.parent.name
        en_path = path.with_name(path.name.replace(".zh.md", ".en.md"))
        translation_status = "missing"
        if en_path.exists():
            en_text = en_path.read_text(encoding="utf-8")
            translation_status = "pending" if "English translation pending" in en_text else "ready"
        rows.append(
            {
                "item_id": f"draft:{slug}:{path.name}",
                "slug": slug,
                "title": title,
                "path": str(path.relative_to(ROOT)),
                "en_path": str(en_path.relative_to(ROOT)) if en_path.exists() else "",
                "translation_status": translation_status,
                "summary": excerpt_markdown(text, 720),
                "mtime": path.stat().st_mtime,
            }
        )
    return rows


def excerpt_markdown(text: str, limit: int) -> str:
    lines = []
    in_frontmatter = False
    for line in text.splitlines():
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if line.startswith("# "):
            continue
        if line.strip():
            lines.append(line.strip())
    flat = " ".join(lines)
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "..."


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def status_of_request(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def translation_queue_cards() -> str:
    requests = sorted(TRANSLATION_REQUESTS.glob("*.md")) if TRANSLATION_REQUESTS.exists() else []
    pending = [(path, status_of_request(path)) for path in requests if status_of_request(path) == "pending"]
    if not pending:
        return "<p class='empty'>No pending translation requests.</p>"
    rows = []
    for path, status in pending[:20]:
        rows.append(f"<li><span>{esc(status)}</span> <code>{esc(path.relative_to(ROOT))}</code></li>")
    return "<ul class='queue'>" + "\n".join(rows) + "</ul>"


def intake_panel() -> str:
    return f"""
<section class="card">
  <h2>Intake</h2>
  <div class="source-strip" aria-label="Default sources">
    <span>Default sources</span>
    <strong>Huaren public search + comments</strong>
    <strong>Xiaohongshu research brief</strong>
    <strong>Public ebook search</strong>
  </div>
  <p class="empty">YouTube, podcasts, saved Xiaohongshu notes, specific Huaren links, and local ebooks go through Curated Inputs below.</p>
  <form method="POST" action="/intake">
    <label>Topic / prompt
      <textarea name="prompt" placeholder="例如：AI时代妈妈如何训练孩子判断力"></textarea>
    </label>
    <label>Keywords
      <input name="keywords" value="AI,孩子,判断力">
    </label>
    <div class="grid">
      <label>Search breadth
        <input name="max_results" type="number" min="1" max="50" value="10">
      </label>
      <label>Comment depth
        <input name="fetch_top" type="number" min="0" max="10" value="3">
      </label>
      <label>Long-form results
        <input name="ebook_limit" type="number" min="1" max="30" value="5">
      </label>
    </div>
    <details class="subpanel">
      <summary>Advanced source controls</summary>
      <label class="check"><input type="checkbox" name="include_community" value="1" checked> include community/forum search</label>
      <label class="check"><input type="checkbox" name="include_longform" value="1" checked> include public ebook search</label>
      <label class="check"><input type="checkbox" name="skip_monitor" value="1"> skip analysis rebuild</label>
      <label>Long-form query override
        <input name="ebook_query" placeholder="默认使用上面的 topic / prompt">
      </label>
      <div class="grid">
        <label>Forum pages
          <input name="pages" type="number" min="1" max="5" value="1">
        </label>
        <label>Thread pages
          <input name="thread_pages" type="number" min="1" max="5" value="1">
        </label>
        <label>Download Gutendex ID
          <input name="ebook_download_id" placeholder="optional">
        </label>
        <label>Format
          <select name="ebook_prefer">
            <option value="">auto</option>
            <option value="txt">txt</option>
            <option value="epub">epub</option>
          </select>
        </label>
      </div>
    </details>
    <div class="actions">
      <span class="empty">Searches the available sources from your topic and saves the results into the knowledge workflow.</span>
      <button type="submit">Run Research Intake</button>
    </div>
  </form>
</section>
<section class="card">
  <h2>Curated Inputs</h2>
  <h3>Saved source</h3>
  <form method="POST" action="/curated-source">
    <div class="grid">
      <label>Source type
        <select name="source_type">
          <option value="xiaohongshu">Xiaohongshu note</option>
          <option value="huaren">Huaren thread</option>
          <option value="youtube">YouTube video</option>
          <option value="podcast">Podcast episode</option>
          <option value="article">Article / other</option>
        </select>
      </label>
      <label>Huaren pages
        <input name="huaren_pages" type="number" min="1" max="5" value="1">
      </label>
    </div>
    <label>Title
      <input name="title" placeholder="optional">
    </label>
    <label>URL
      <input name="url" placeholder="optional, Huaren URL can trigger comment capture">
    </label>
    <label>Saved text / transcript / comments
      <textarea name="content" placeholder="粘贴你事先保存的小红书笔记、评论、YouTube transcript、文章摘录等"></textarea>
    </label>
    <label class="check"><input type="checkbox" name="fetch_transcript" value="1"> fetch transcript from URL</label>
    <label>Why this matters
      <textarea name="user_note" placeholder="你为什么觉得它值得进入知识库？这会成为高价值 feedback 数据。"></textarea>
    </label>
    <div class="actions">
      <label class="check"><input type="checkbox" name="no_ai" value="1" checked> no AI call</label>
      <button type="submit">Save Curated Source</button>
    </div>
  </form>
  <div class="subpanel">
    <h3>Local ebook</h3>
  </div>
  <form method="POST" action="/ebook-upload" enctype="multipart/form-data">
    <label>Ebook file
      <input name="ebook_file" type="file" accept=".txt,.epub,.md,.pdf">
    </label>
    <div class="grid">
      <label>Title override
        <input name="title" placeholder="optional">
      </label>
      <label>Max chapters
        <input name="max_chapters" type="number" min="1" max="50" value="8">
      </label>
      <label>Analysis engine
        <select name="analysis_engine">
          <option value="notebooklm">NotebookLM</option>
          <option value="local">Local fallback</option>
        </select>
      </label>
    </div>
    <label>Why this book matters
      <textarea name="user_note" placeholder="你为什么选中这本书？以后可以用来学习你的选书标准。"></textarea>
    </label>
    <div class="actions">
      <label class="check"><input type="checkbox" name="no_ai" value="1" checked> curated-note no AI</label>
      <button type="submit">Analyze Uploaded Ebook</button>
    </div>
  </form>
</section>
"""


def system_panel() -> str:
    return f"""
<section class="card">
  <h2>System</h2>
  <form method="POST" action="/memory-reflect">
    <div class="actions">
      <span>Promote raw feedback and curated choices into principles.</span>
      <button type="submit">Update Memory Principles</button>
    </div>
  </form>
  <form method="POST" action="/smoke-test">
    <div class="actions">
      <span>Run local smoke test for the downstream workflow.</span>
      <button type="submit">Run Smoke Test</button>
    </div>
  </form>
</section>
<section class="card">
  <h2>Translation Queue</h2>
  {translation_queue_cards()}
</section>
"""


def material_cards() -> str:
    candidates = load_candidates()
    cards = []
    for item in candidates:
        scores = item.get("scores", {})
        candidate_id = str(item.get("candidate_id", ""))
        cards.append(
            f"""
<article class="card">
  <div class="meta">
    <span>{esc(item.get("source_type"))}</span>
    <span>{esc(item.get("source_priority", "standard"))}</span>
    <span>Score {esc(item.get("score"))}</span>
    <span>{esc(", ".join(item.get("topics", [])))}</span>
  </div>
  <h2>{esc(item.get("title"))}</h2>
  <p class="summary">{esc(item.get("summary"))}</p>
  <p><strong>Angle:</strong> {esc(item.get("recommended_angle"))}</p>
  <details>
    <summary>Scores and source</summary>
    <pre>{esc(json.dumps(scores, ensure_ascii=False, indent=2))}</pre>
    <p><code>{esc(item.get("source_path"))}</code></p>
  </details>
  <form method="POST" action="/feedback">
    <input type="hidden" name="item_id" value="{esc(candidate_id)}">
    <input type="hidden" name="track" value="material">
    <input type="hidden" name="feedback_type" value="material_review">
    <input type="hidden" name="item_type" value="analysis">
    <input type="hidden" name="source_path" value="{esc(item.get("source_path"))}">
    <div class="grid">
      <label>Decision
        <select name="decision">
          <option value="keep">keep</option>
          <option value="deepen">deepen</option>
          <option value="rewrite">rewrite</option>
          <option value="publish">publish</option>
          <option value="skip">skip</option>
          <option value="archive">archive</option>
        </select>
      </label>
      {score_input("relevance", 3)}
      {score_input("insight", 3)}
      {score_input("voice_match", 3)}
      {score_input("publishability", 3)}
      {score_input("life_reflection_value", 3)}
    </div>
    <label>Tags
      <input name="tags" placeholder="too_ai, strong_mechanism, worth_deepening">
    </label>
    <label>Raw feedback
      <textarea name="feedback_text" placeholder="原样写下你的判断、批注或修改建议"></textarea>
    </label>
    <label>Rewrite instruction
      <textarea name="rewrite_instruction" placeholder="如果要 AI 改，下一轮怎么改？"></textarea>
    </label>
    <label>Article slug
      <input name="pages_slug" placeholder="可留空；保存反馈后可同时生成双语 Pages 草稿">
    </label>
    <div class="actions">
      <label class="check"><input type="checkbox" name="memory_candidate" value="1"> memory candidate</label>
      <label class="check"><input type="checkbox" name="create_pages_draft" value="1"> Pages draft</label>
      <button type="submit">Save Feedback</button>
    </div>
  </form>
</article>
"""
        )

    return "\n".join(cards) if cards else "<p class='empty'>No pending materials. Build the Review Inbox first.</p>"


def draft_cards() -> str:
    drafts = load_drafts()
    cards = []
    for item in drafts:
        cards.append(
            f"""
<article class="card">
  <div class="meta">
    <span>pages draft</span>
    <span>{esc(item.get("slug"))}</span>
    <span>English: {esc(item.get("translation_status"))}</span>
  </div>
  <h2>{esc(item.get("title"))}</h2>
  <p class="summary">{esc(item.get("summary"))}</p>
  <details>
    <summary>Draft path</summary>
    <p><code>{esc(item.get("path"))}</code></p>
    <p><code>{esc(item.get("en_path"))}</code></p>
  </details>
  <form method="POST" action="/feedback">
    <input type="hidden" name="track" value="draft">
    <input type="hidden" name="feedback_type" value="draft_review">
    <input type="hidden" name="item_type" value="draft">
    <input type="hidden" name="item_id" value="{esc(item.get("item_id"))}">
    <input type="hidden" name="source_path" value="{esc(item.get("path"))}">
    <input type="hidden" name="draft_path_before" value="{esc(item.get("path"))}">
    <input type="hidden" name="article_slug" value="{esc(item.get("slug"))}">
    <input type="hidden" name="publish_target" value="pages">
    <div class="grid">
      <label>Decision
        <select name="decision">
          <option value="rewrite">rewrite</option>
          <option value="publish">publish</option>
          <option value="deepen">deepen</option>
          <option value="archive">archive</option>
        </select>
      </label>
      {score_input("relevance", 4)}
      {score_input("insight", 4)}
      {score_input("voice_match", 3)}
      {score_input("publishability", 3)}
      {score_input("life_reflection_value", 4)}
    </div>
    <label>Detailed feedback
      <textarea name="feedback_text" placeholder="{esc(render_profile("结构、论证、标题、语气、可信度、哪里不像 Creator"))}"></textarea>
    </label>
    <label>Revision request
      <textarea name="rewrite_instruction" placeholder="下一版具体怎么改"></textarea>
    </label>
    <label>Blocking issues
      <input name="blocking_issues" placeholder="too_generic, weak_opening, needs_personal_story">
    </label>
    <label>Tags
      <input name="tags" placeholder="strong_angle, too_ai, publish_ready">
    </label>
    <div class="actions">
      <label class="check"><input type="checkbox" name="approved_for_publish" value="1"> approved</label>
      <label class="check"><input type="checkbox" name="memory_candidate" value="1"> memory candidate</label>
      <button type="submit">Save Draft Review</button>
    </div>
  </form>
</article>
"""
        )
    return "\n".join(cards) if cards else "<p class='empty'>No article drafts yet.</p>"


def page(track: str = "materials", message: str = "") -> str:
    panels = {
        "intake": intake_panel,
        "materials": material_cards,
        "drafts": draft_cards,
        "system": system_panel,
    }
    if track not in panels:
        track = "materials"
    body = panels[track]()
    active_intake = "active" if track == "intake" else ""
    active_materials = "active" if track == "materials" else ""
    active_drafts = "active" if track == "drafts" else ""
    active_system = "active" if track == "system" else ""
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(creator_name())} Knowledge Flywheel</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #202124;
      --muted: #64706d;
      --line: #d8ddd8;
      --paper: #fbfaf7;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-dark: #115e59;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(251, 250, 247, 0.96);
    }}
    h1 {{ margin: 0; font-size: 22px; }}
    nav {{
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }}
    nav a {{
      color: var(--ink);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 10px;
      background: #fff;
      font-weight: 700;
    }}
    nav a.active {{
      border-color: var(--accent);
      color: #fff;
      background: var(--accent);
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 22px;
    }}
    .notice {{
      margin: 12px 0 0;
      color: var(--accent-dark);
      font-weight: 600;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 0 0 18px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .meta span {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      background: #f6f7f4;
    }}
    h2 {{ margin: 10px 0 8px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    summary {{ cursor: pointer; font-weight: 700; }}
    .summary {{ white-space: pre-wrap; }}
    .source-strip {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin: 10px 0 6px;
    }}
    .source-strip span {{
      color: var(--muted);
      font-weight: 700;
    }}
    .source-strip strong {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 9px;
      background: #f6f7f4;
      font-size: 13px;
    }}
    .subpanel {{
      border-top: 1px solid var(--line);
      margin-top: 16px;
      padding-top: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    label {{
      display: grid;
      gap: 5px;
      margin-top: 10px;
      font-weight: 600;
    }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: #fff;
    }}
    textarea {{ min-height: 86px; resize: vertical; }}
    .actions {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 12px;
    }}
    .check {{ display: flex; grid-template-columns: none; align-items: center; gap: 8px; margin: 0; }}
    .check input {{ width: auto; }}
    button {{
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 9px 14px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ background: var(--accent-dark); }}
    pre {{
      overflow: auto;
      background: #f6f7f4;
      border-radius: 6px;
      padding: 10px;
    }}
    .empty {{ color: var(--muted); }}
    .queue {{
      margin: 0;
      padding-left: 20px;
    }}
    .queue li {{ margin: 8px 0; }}
    .queue span {{
      display: inline-block;
      min-width: 64px;
      color: var(--accent-dark);
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{esc(creator_name())} Knowledge Flywheel</h1>
    <nav>
      <a class="{active_intake}" href="/?track=intake">Intake</a>
      <a class="{active_materials}" href="/?track=materials">Materials</a>
      <a class="{active_drafts}" href="/?track=drafts">Drafts</a>
      <a class="{active_system}" href="/?track=system">System</a>
    </nav>
    {f'<p class="notice">{esc(message)}</p>' if message else ''}
  </header>
  <main>{body}</main>
</body>
</html>"""


def score_input(name: str, default: int) -> str:
    return f"""<label>{name.replace('_', ' ').title()}
      <input name="{name}" type="number" min="1" max="5" value="{default}">
    </label>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        message = qs.get("message", [""])[0]
        track = qs.get("track", ["materials"])[0]
        self.respond(page(track, message))

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/feedback":
            return self.handle_feedback()
        if self.path == "/intake":
            return self.handle_intake()
        if self.path == "/ebook-upload":
            return self.handle_ebook_upload()
        if self.path == "/curated-source":
            return self.handle_curated_source()
        if self.path == "/smoke-test":
            return self.handle_smoke_test()
        if self.path == "/memory-reflect":
            return self.handle_memory_reflect()
        self.send_error(404)

    def read_form(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        return urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))

    def redirect(self, track: str, msg: str) -> None:
        self.send_response(303)
        self.send_header("Location", f"/?track={track}&message=" + urllib.parse.quote(msg))
        self.end_headers()

    def handle_intake(self) -> None:
        data = self.read_form()
        value = lambda key, default="": data.get(key, [default])[0]
        prompt = value("prompt") or "AI时代妈妈如何训练孩子判断力"
        keywords = value("keywords") or "AI,孩子,判断力"
        cmd = [
            "intake-test",
            "--prompt",
            prompt,
            "--keywords",
            keywords,
            "--pages",
            value("pages", "1"),
            "--max-results",
            value("max_results", "10"),
            "--fetch-top",
            value("fetch_top", "0"),
            "--thread-pages",
            value("thread_pages", "1"),
        ]
        if not value("include_community", ""):
            cmd.append("--skip-huaren")
        if value("skip_monitor"):
            cmd.append("--skip-monitor")
        result = run_brand_factory(*cmd)
        messages = []
        if result.returncode == 0:
            messages.append("Community intake finished.")
        else:
            messages.append("Community intake failed: " + (result.stderr or result.stdout))
        if result.returncode == 0 and value("include_longform", ""):
            ebook_query = value("ebook_query") or prompt
            ebook_cmd = ["ebook", "search", "--query", ebook_query, "--limit", value("ebook_limit", "5")]
            download_id = value("ebook_download_id").strip()
            prefer = value("ebook_prefer").strip()
            if download_id:
                ebook_cmd.extend(["--download-id", download_id])
            if prefer:
                ebook_cmd.extend(["--prefer", prefer])
            ebook_result = run_brand_factory(*ebook_cmd)
            if ebook_result.returncode == 0:
                messages.append("Ebook intake finished.")
            else:
                messages.append("Ebook intake failed: " + (ebook_result.stderr or ebook_result.stdout))
        msg = " ".join(messages)
        self.redirect("intake", msg[-800:])
        return

    def handle_curated_source(self) -> None:
        data = self.read_form()
        value = lambda key, default="": data.get(key, [default])[0].strip()
        source_type = value("source_type", "article")
        title = value("title")
        url = value("url")
        content = value("content")
        user_note = value("user_note")
        transcript_message = ""
        if value("fetch_transcript"):
            if source_type not in {"youtube", "podcast"}:
                self.redirect("intake", "Transcript fetch only supports YouTube and Podcast sources.")
                return
            if not url:
                self.redirect("intake", "Transcript fetch failed: add a YouTube or podcast URL.")
                return
            transcript_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "fetch_transcript.py"),
                    "--source-type",
                    source_type,
                    "--url",
                    url,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            if transcript_result.returncode != 0:
                self.redirect("intake", "Transcript fetch failed: " + (transcript_result.stderr or transcript_result.stdout)[-700:])
                return
            fetched_text = transcript_result.stdout.strip()
            content = "\n\n".join(part for part in [content, "## Fetched transcript\n\n" + fetched_text] if part)
            transcript_message = "Transcript fetched."
        if not url and not content:
            self.redirect("intake", "Curated source failed: add a URL or pasted text.")
            return

        note_path = write_curated_source_note(source_type, title, url, content, user_note)
        messages = [f"Saved curated source: {note_path.relative_to(ROOT)}"]
        if transcript_message:
            messages.append(transcript_message)

        if source_type == "huaren" and url:
            huaren_cmd = ["huaren", "thread", url, "--pages", value("huaren_pages", "1")]
            if value("no_ai"):
                huaren_cmd.append("--no-ai")
            huaren_result = run_brand_factory(*huaren_cmd)
            if huaren_result.returncode == 0:
                messages.append("Huaren comments captured.")
            else:
                messages.append("Huaren comment capture failed: " + (huaren_result.stderr or huaren_result.stdout))

        monitor_cmd = ["monitor", "--once"]
        if value("no_ai"):
            monitor_cmd.append("--no-ai")
        monitor_result = run_brand_factory(*monitor_cmd)
        if monitor_result.returncode == 0:
            messages.append("Curated source analyzed.")
        else:
            messages.append("Curated analysis failed: " + (monitor_result.stderr or monitor_result.stdout))

        review_result = run_brand_factory("review", "build")
        if review_result.returncode == 0:
            messages.append("Review inbox rebuilt.")
        else:
            messages.append("Review rebuild failed: " + (review_result.stderr or review_result.stdout))
        self.redirect("intake", " ".join(messages)[-800:])
        return

    def handle_ebook_upload(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )
        file_item = form["ebook_file"] if "ebook_file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            self.redirect("intake", "Upload failed: choose a .txt, .md, .epub, or .pdf file first.")
            return
        filename = safe_filename(file_item.filename)
        if Path(filename).suffix.lower() not in {".txt", ".md", ".epub", ".pdf"}:
            self.redirect("intake", "Upload failed: supported files are .txt, .md, .epub, and .pdf.")
            return
        BOOKS_RAW.mkdir(parents=True, exist_ok=True)
        dest = unique_path(BOOKS_RAW, filename)
        dest.write_bytes(file_item.file.read())

        title = form.getfirst("title", "").strip()
        user_note = form.getfirst("user_note", "").strip()
        engine = form.getfirst("analysis_engine", "notebooklm")
        curated_note = write_curated_book_note(dest, title, user_note)
        metadata_path = write_book_curation_metadata(dest, title, user_note)
        messages = [
            f"Saved curated book: {dest.relative_to(ROOT)}",
            f"Book curation note: {curated_note.relative_to(ROOT)}",
            f"Book metadata: {metadata_path.relative_to(ROOT)}",
        ]

        if engine == "notebooklm":
            notebook_title = title or dest.stem
            result = run_brand_factory(
                "notebooklm",
                "--create-title",
                notebook_title,
                "--source",
                str(dest),
                "--prompt-file",
                "prompts/book_chapter_analysis.md",
                "--output-name",
                f"{dest.stem}-notebooklm",
            )
            if result.returncode == 0:
                messages.append("NotebookLM analysis saved to book vault.")
            else:
                messages.append("NotebookLM analysis failed: " + (result.stderr or result.stdout))
        else:
            if dest.suffix.lower() == ".pdf":
                messages.append("Local fallback does not support PDF. Use NotebookLM for PDF books.")
            else:
                cmd = ["ebook", "analyze", str(dest), "--max-chapters", form.getfirst("max_chapters", "8")]
                if title:
                    cmd.extend(["--title", title])
                if form.getfirst("no_ai"):
                    cmd.append("--no-ai")
                result = run_brand_factory(*cmd)
                if result.returncode == 0:
                    messages.append("Local ebook chapters analyzed.")
                else:
                    messages.append("Local ebook analysis failed: " + (result.stderr or result.stdout))

        monitor_cmd = ["monitor", "--once"]
        if form.getfirst("no_ai"):
            monitor_cmd.append("--no-ai")
        monitor_result = run_brand_factory(*monitor_cmd)
        if monitor_result.returncode == 0:
            messages.append("Curated book added to review workflow.")
        else:
            messages.append("Curated book review workflow failed: " + (monitor_result.stderr or monitor_result.stdout))

        review_result = run_brand_factory("review", "build")
        if review_result.returncode == 0:
            messages.append("Review inbox rebuilt.")
        else:
            messages.append("Review rebuild failed: " + (review_result.stderr or review_result.stdout))
        self.redirect("intake", " ".join(messages)[-800:])
        return

    def handle_smoke_test(self) -> None:
        result = run_brand_factory("smoke-test", "--skip-ui")
        msg = "Smoke test passed." if result.returncode == 0 else "Smoke test failed: " + (result.stderr or result.stdout)
        self.redirect("system", msg[-800:])
        return

    def handle_memory_reflect(self) -> None:
        result = run_brand_factory("memory", "reflect")
        msg = "Memory principles updated." if result.returncode == 0 else "Memory reflection failed: " + (result.stderr or result.stdout)
        self.redirect("system", msg[-800:])
        return

    def handle_feedback(self) -> None:
        if self.path != "/feedback":
            self.send_error(404)
            return
        data = self.read_form()
        value = lambda key, default="": data.get(key, [default])[0]
        cmd = [
            sys.executable,
            str(SCRIPTS / "record_feedback.py"),
            "--item-id",
            value("item_id"),
            "--feedback-type",
            value("feedback_type", "material_review"),
            "--item-type",
            value("item_type", "analysis"),
            "--source-path",
            value("source_path"),
            "--decision",
            value("decision", "keep"),
            "--relevance",
            value("relevance", "3"),
            "--insight",
            value("insight", "3"),
            "--voice-match",
            value("voice_match", "3"),
            "--publishability",
            value("publishability", "3"),
            "--life-reflection-value",
            value("life_reflection_value", "3"),
            "--tags",
            value("tags"),
            "--feedback-text",
            value("feedback_text"),
            "--rewrite-instruction",
            value("rewrite_instruction"),
            "--article-slug",
            value("article_slug"),
            "--publish-target",
            value("publish_target"),
            "--draft-path-before",
            value("draft_path_before"),
            "--blocking-issues",
            value("blocking_issues"),
        ]
        if value("approved_for_publish"):
            cmd.append("--approved-for-publish")
        if value("memory_candidate"):
            cmd.append("--memory-candidate")
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        if result.returncode == 0 and value("create_pages_draft"):
            draft_cmd = [
                sys.executable,
                str(SCRIPTS / "generate_pages_article.py"),
                "--candidate-id",
                value("item_id"),
            ]
            if value("pages_slug"):
                draft_cmd.extend(["--slug", value("pages_slug")])
            draft_result = subprocess.run(draft_cmd, cwd=ROOT, text=True, capture_output=True)
            if draft_result.returncode == 0:
                msg = "Saved feedback and generated bilingual Pages draft."
            else:
                msg = "Saved feedback, but Pages draft failed: " + (draft_result.stderr or draft_result.stdout)
        else:
            msg = "Saved feedback." if result.returncode == 0 else f"Failed: {result.stderr or result.stdout}"
        redirect_track = "drafts" if value("track") == "draft" else "materials"
        self.redirect(redirect_track, msg)
        return

    def respond(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Review UI running at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
