#!/usr/bin/env python3
"""Small local HITL review UI for Creator Brand Factory."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INBOX = ROOT / "insight_vault" / "60_Review_Inbox"
CANDIDATES_PATH = INBOX / "candidates.jsonl"
DRAFTS = ROOT / "content" / "pages_drafts"


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
        rows.append(
            {
                "item_id": f"draft:{slug}:{path.name}",
                "slug": slug,
                "title": title,
                "path": str(path.relative_to(ROOT)),
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
  </div>
  <h2>{esc(item.get("title"))}</h2>
  <p class="summary">{esc(item.get("summary"))}</p>
  <details>
    <summary>Draft path</summary>
    <p><code>{esc(item.get("path"))}</code></p>
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
      <textarea name="feedback_text" placeholder="结构、论证、标题、语气、可信度、哪里不像 Creator"></textarea>
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
    is_drafts = track == "drafts"
    body = draft_cards() if is_drafts else material_cards()
    active_materials = "active" if not is_drafts else ""
    active_drafts = "active" if is_drafts else ""
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Creator Review Inbox</title>
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
    .summary {{ white-space: pre-wrap; }}
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
  </style>
</head>
<body>
  <header>
    <h1>Creator Review Inbox</h1>
    <nav>
      <a class="{active_materials}" href="/?track=materials">Materials</a>
      <a class="{active_drafts}" href="/?track=drafts">Drafts</a>
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
        if self.path != "/feedback":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
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
        self.send_response(303)
        redirect_track = "drafts" if value("track") == "draft" else "materials"
        self.send_header("Location", f"/?track={redirect_track}&message=" + urllib.parse.quote(msg))
        self.end_headers()

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
