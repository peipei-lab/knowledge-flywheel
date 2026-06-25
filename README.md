# Knowledge Flywheel

This is a local automation kit for a weekly loop:

1. Curated AI sources in.
2. AI-assisted extraction through Creator's lens.
3. Weekly brief plus Xiaohongshu, X/Twitter, and video drafts out.
4. Published ideas flow back into a private knowledge base.
5. Creator adds 1-2 real scientist-mom reflections.

## Unified Console

Daily use should start from one entry point:

```bash
cd /path/to/knowledge-flywheel
python3 brand_factory.py
```

This opens a menu for weekly briefs, Huaren search/thread comments, Xiaohongshu manual research/import, public ebook search, ebook chapter analysis, NotebookLM, and local capture monitoring.

By default, every successful content-producing action automatically syncs all Obsidian-compatible vaults:

- `obsidian_vault/`
- `raw_capture_vault/`
- `insight_vault/`
- `book_vault/`

Use `--no-sync` only when debugging or running several commands in a batch. The standalone `sync` command is kept as a maintenance fallback, not as a normal workflow step.

You can also call the same interface with commands:

```bash
python3 brand_factory.py weekly
python3 brand_factory.py huaren search --keywords "AI,孩子,教育,职场" --no-ai
python3 brand_factory.py huaren thread "https://huaren.us/showtopic.html?topicid=3194904&fid=333" --pages 1 --no-ai
python3 brand_factory.py xhs brief --prompt "AI时代妈妈对孩子学习编程和升学焦虑的真实讨论"
python3 brand_factory.py xhs import path/to/xiaohongshu-notes.json
python3 brand_factory.py ebook search --query "education children thinking" --limit 10
python3 brand_factory.py ebook analyze content/books/raw/book-file.txt --max-chapters 8 --no-ai
python3 brand_factory.py monitor --once --no-ai
python3 brand_factory.py pages draft --candidate-id CANDIDATE_ID --slug my-article --no-ai
python3 brand_factory.py pages publish --slug my-article --stage-only
python3 brand_factory.py smoke-test
python3 brand_factory.py intake-test --prompt "AI时代妈妈如何训练孩子判断力" --keywords "AI,孩子,判断力"
python3 brand_factory.py paths
python3 brand_factory.py sync  # maintenance fallback only
```

## Smoke Test

Run a local end-to-end test without publishing to a real GitHub Pages repo:

```bash
python3 brand_factory.py smoke-test
```

This checks Python compilation, Review Inbox generation, Pages draft generation, Codex translation queue creation, local staging publish, and Obsidian sync. The Review UI check is best-effort by default because some sandboxed environments block localhost requests. Use `--require-ui` when running from a normal terminal and you want UI reachability to be a hard failure.

## Intake Test

Run a prompt/keyword-driven intake test:

```bash
python3 brand_factory.py intake-test \
  --prompt "AI时代妈妈如何训练孩子判断力" \
  --keywords "AI,孩子,判断力"
```

This creates a Xiaohongshu manual research brief and runs Huaren public search. To also fetch comments from the top ranked Huaren results, add:

```bash
python3 brand_factory.py intake-test \
  --prompt "AI时代妈妈如何训练孩子判断力" \
  --keywords "AI,孩子,判断力" \
  --fetch-top 3
```

Use `--skip-huaren` for an offline/local-only test, or `--skip-monitor` when you only want to test search output without rebuilding the analysis inbox.

## HITL Review Inbox

Build the review inbox:

```bash
python3 brand_factory.py review build --limit 20
```

Start the local review UI:

```bash
python3 brand_factory.py review ui --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

The browser UI has four tabs:

- `Intake`: run prompt/keyword-driven intake from the browser. It can create a Xiaohongshu research brief, run Huaren public search, optionally fetch top Huaren thread comments, and optionally search public-domain ebooks. YouTube/podcast transcript intake is not enabled yet; paste transcripts into the raw capture vault for now.
- `Materials`: raw analyses the AI thinks may be useful or interesting. Your feedback here trains source/topic selection, curiosity fit, and what deserves deeper work.
- `Drafts`: article drafts generated from a specific topic, prompt, or reviewed material. Your feedback here trains structure, voice, argument quality, publishability, and revision standards.
- `System`: run the local smoke test and inspect pending Codex translation requests.

Every saved review appends an immutable raw feedback event to:

```text
insight_vault/30_Creator_Feedback/raw_feedback_events.jsonl
```

In the browser UI, check `Pages draft` while saving feedback to turn a candidate into a bilingual GitHub Pages draft. This creates:

- `content/pages_drafts/SLUG/YYYY-MM-DD-SLUG.zh.md`
- `content/pages_drafts/SLUG/YYYY-MM-DD-SLUG.en.md`
- `insight_vault/70_Draft_Revisions/SLUG/`

If `OPENAI_API_KEY` is set, the system can generate the Chinese article and English adaptation. Without it, it creates a structured Chinese draft plus an English translation prompt, so unfinished AI work is never confused with a publish-ready article.

To publish into a real GitHub Pages repo, set `config/github_pages.json`:

```json
{
  "repo_path": "/path/to/your/github-pages-repo",
  "posts_dir": "_posts"
}
```

Then run:

```bash
python3 brand_factory.py pages publish --slug my-article
```

To publish and commit in one step:

```bash
python3 brand_factory.py pages publish --slug my-article --git-commit
```

Use `--git-push` only after the repo path, branch, and GitHub auth are confirmed.

Use `--stage-only` to test the copy step inside `content/pages_published/` before touching the real repo.

The older scripts in `scripts/` are still kept as the engine layer. You normally do not need to remember them.

## Weekly Workflow

Run:

```bash
cd /path/to/knowledge-flywheel
bash scripts/weekly_run.sh
```

If you want AI generation, set an API key first:

```bash
export OPENAI_API_KEY="..."
bash scripts/weekly_run.sh
```

If you do not set `OPENAI_API_KEY`, the workflow still creates an AI-ready prompt pack you can paste into your preferred model.

## What To Edit

- `config/sources.json`: your 5-10 high-signal sources.
- `config/brand_profile.json`: Creator positioning, audience, and signature lens.
- `prompts/deep_extract.md`: per-article extraction prompt.
- `prompts/weekly_synthesis.md`: weekly synthesis prompt.
- `prompts/knowledge_atom.md`: converts content into reusable knowledge atoms.
- `content/knowledge/problem_backlog/problem_backlog.md`: your long-term question map.

## Outputs

- `content/inbox/YYYY-MM-DD/`: fetched RSS items.
- `content/briefs/YYYY-MM-DD-prompt-pack.md`: prompt pack for the LLM.
- `content/briefs/YYYY-MM-DD-weekly-brief.md`: weekly brief.
- `content/social/`: Xiaohongshu, X/Twitter, and video drafts.
- `content/pages_drafts/`: reviewed long-form GitHub Pages article drafts in Chinese and English.
- `content/pages_published/`: local staging output for bilingual Pages posts.
- `content/knowledge/atoms/`: reusable knowledge atoms for your second brain.
- `content/knowledge/reflections/`: weekly cognitive reflection reports.
- `content/community/huaren/`: keyword/prompt-triggered Huaren forum candidate insights.
- `obsidian_vault/`: an Obsidian-compatible copy of the knowledge system.

## Manual 1-2 Hour Rhythm

1. Run the script.
2. Open the weekly brief.
3. Delete weak items and keep the strongest 1-3 ideas.
4. Add one honest paragraph in `Creator 人工补充区`.
5. Open the weekly cognitive reflection and update your own thinking.
6. Record the video from `content/social/*-video-outline.md`.
7. Publish or schedule the social drafts.

## Knowledge Flywheel

The system is no longer only:

```text
Input -> Brief -> Publish
```

It is now:

```text
Input -> Brief -> Social Drafts -> Knowledge Atoms -> Problem Backlog Match -> Cognitive Reflection
```

Use `content/knowledge/problem_backlog/problem_backlog.md` as your living map of long-term questions. The weekly reflection tries to connect new ideas back to this map.

## Huaren Forum Search

This workflow supports on-demand Huaren forum search plus optional public thread/comment capture. It is not a full crawler.

The daily path is guided search:

```bash
python3 brand_factory.py huaren guided \
  --prompt "我想找北美华人妈妈关于孩子AI时代学习、编程、升学焦虑的真实讨论" \
  --auto-fetch-top 10 \
  --no-ai
```

This searches candidate posts, ranks them by keyword/prompt match score, then fetches comments from the top 10 candidates.

You can also run guided mode without `--auto-fetch-top`; it will show a numbered candidate list. Enter values like `2,3,4,10` or `1-5` to fetch multiple threads. Press Enter to fetch the default top 10.

If you already have a specific Huaren URL, use the precise thread capture command:

```bash
python3 brand_factory.py huaren thread "https://huaren.us/showtopic.html?topicid=3194904&fid=333" --pages 1 --no-ai
```

All successful actions sync to Obsidian automatically.

Lower-level script examples:

Search by keywords:

```bash
python3 scripts/search_huaren.py --keywords "AI,孩子,教育,职场" --no-ai
```

Search by a natural-language prompt:

```bash
python3 scripts/search_huaren.py --prompt "我想找北美华人妈妈关于孩子AI时代学习、编程、升学焦虑的真实讨论" --no-ai
```

Outputs:

- `content/community/huaren/YYYY-MM-DD-huaren-candidates.md`
- `content/community/prompts/YYYY-MM-DD-huaren-insight-prompt.md`

Fetch public Huaren thread posts/comments after you pick a candidate URL:

```bash
python3 scripts/fetch_huaren_thread.py "https://huaren.us/showtopic.html?topicid=3194904&fid=333" --pages 1 --no-ai
```

The thread fetcher saves short, privacy-safe excerpts and an AI-ready prompt. It does not store usernames or use comments as publishable copy.

## Xiaohongshu Import

Xiaohongshu is supported through manual import, not automated scraping. Save or export posts/comments yourself as JSON, CSV, Markdown, or text, then run:

```bash
python3 scripts/import_xiaohongshu.py path/to/xiaohongshu-notes.json
python3 scripts/sync_obsidian.py
```

Suggested JSON shape:

```json
[
  {
    "title": "标题",
    "url": "https://...",
    "body": "帖子正文",
    "likes": "123",
    "comments": ["评论1", "评论2"]
  }
]
```

This keeps the workflow useful without bypassing login, anti-bot controls, or platform boundaries.

Create a prompt-driven manual research brief:

```bash
python3 scripts/xiaohongshu_research_brief.py \
  --prompt "我想找AI时代妈妈对孩子学习编程和升学焦虑的真实讨论"
```

This creates a search checklist and JSON import template under `content/community/xiaohongshu_research/`.

## Public Ebook Workflow

The ebook workflow only auto-downloads public-domain/open-license/open-access books, or analyzes files you already own.

Search public-domain books:

```bash
python3 scripts/search_public_ebooks.py --query "education children thinking" --limit 10
```

Download one result from the search list:

```bash
python3 scripts/search_public_ebooks.py --query "education children thinking" --download-id gutenberg-XXXX
```

Analyze a downloaded or user-owned `.txt` / `.epub`:

```bash
python3 scripts/analyze_ebook.py content/books/raw/book-file.txt --max-chapters 8 --no-ai
python3 scripts/sync_book_vault.py
```

Outputs:

- `content/books/raw/`: downloaded or imported ebooks.
- `content/books/chapters/`: split chapter text.
- `content/books/analyses/`: chapter analyses.
- `book_vault/`: Obsidian-compatible ebook vault.

Analysis modes include knowledge atoms, Socratic questions, and Creator's AI-scientist-mom lens.

## Optional NotebookLM Adapter

There is an optional adapter for the unofficial `teng-lin/notebooklm-py` CLI. This is not a Google official API and uses undocumented Google APIs, so keep it optional and expect breakage/rate limits.

This project keeps the CLI in its own virtual environment:

```bash
outputs/brand_factory/.venv/bin/notebooklm --help
outputs/brand_factory/.venv/bin/notebooklm login
```

After you authenticate, you can run:

```bash
python3 scripts/notebooklm_adapter.py \
  --create-title "Creator Book Analysis" \
  --source content/books/raw/book-file.pdf \
  --prompt-file prompts/book_chapter_analysis.md

python3 scripts/sync_book_vault.py
```

This saves NotebookLM output into:

```text
book_vault/50_NotebookLM_Outputs
```

## Obsidian

After each weekly run, the workflow syncs Markdown files into:

```text
/path/to/knowledge-flywheel/obsidian_vault
```

Open that folder in Obsidian as a vault. Start from `Home.md`, then use Graph View to inspect links between knowledge atoms, problem backlog, weekly reflections, and content drafts.

## Capture Monitor

There are now two dedicated Obsidian-compatible vaults:

- `raw_capture_vault/`: raw Huaren/Xiaohongshu/community captures.
- `insight_vault/`: generated analyses, knowledge atoms, problem backlog, and reflections.

Open both folders in Obsidian if you want to see raw evidence separately from distilled insights.

Run one scan:

```bash
python3 scripts/monitor_capture_vault.py --once --no-ai
```

Run a local continuous monitor:

```bash
python3 scripts/monitor_capture_vault.py --interval 30 --no-ai
```

When a new `.md`, `.txt`, `.json`, or `.csv` appears in:

- `raw_capture_vault/00_Inbox`
- `raw_capture_vault/10_Huaren_Raw`
- `raw_capture_vault/20_Xiaohongshu_Raw`

the monitor writes an analysis note into:

```text
insight_vault/10_Analyses
```

Without an API key, the analysis uses local heuristics to surface classic replies, debate candidates, and problem-backlog prompts. With `OPENAI_API_KEY`, omit `--no-ai` for deeper AI analysis.

## Notes

RSS feeds change sometimes. If a source stops working, replace its `url` in `config/sources.json`.
