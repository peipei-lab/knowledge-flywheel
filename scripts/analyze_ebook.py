#!/usr/bin/env python3
"""Split a user-owned/public-domain ebook into chapters and create Obsidian analyses."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROMPT_TEMPLATE = ROOT / "prompts" / "book_chapter_analysis.md"
CHAPTER_DIR = ROOT / "content" / "books" / "chapters"
ANALYSIS_DIR = ROOT / "content" / "books" / "analyses"
PROMPT_DIR = ROOT / "content" / "books" / "prompts"


def clean_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def read_txt(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_epub(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith((".html", ".xhtml", ".htm"))]
        for name in sorted(names):
            raw = archive.read(name).decode("utf-8", errors="replace")
            parts.append(clean_text(raw))
    return "\n\n".join(parts)


def read_book(path: Path) -> str:
    if path.suffix.lower() == ".epub":
        return read_epub(path)
    return read_txt(path)


def split_chapters(text: str, max_chapters: int, min_chars: int) -> list[tuple[str, str]]:
    patterns = [
        r"(?im)^\s*(chapter\s+[ivxlcdm\d]+[^\n]*)$",
        r"(?m)^\s*(第[一二三四五六七八九十百\d]+章[^\n]*)$",
    ]
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text))
        if len(matches) >= 2:
            break
    chapters: list[tuple[str, str]] = []
    if len(matches) >= 2:
        for index, match in enumerate(matches[:max_chapters]):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            title = clean_text(match.group(1))
            body = clean_text(text[start:end])
            if len(body) >= min_chars:
                chapters.append((title, body))
    else:
        chunk_size = 12000
        for index, start in enumerate(range(0, min(len(text), max_chapters * chunk_size), chunk_size), 1):
            body = clean_text(text[start : start + chunk_size])
            if len(body) >= min_chars:
                chapters.append((f"Part {index}", body))
    return chapters[:max_chapters]


def call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": "You analyze book chapters into simplified-Chinese knowledge atoms and Socratic questions."},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks).strip()


def heuristic_analysis(book_title: str, chapter_title: str, body: str) -> str:
    sentences = re.split(r"(?<=[。！？.!?])\s+", body)
    first_sentences = " ".join(sentences[:5])[:1000]
    keywords = [word for word in ["孩子", "教育", "学习", "女性", "职业", "AI", "家庭", "思考", "习惯", "问题"] if word in body]
    return f"""# {book_title} - {chapter_title}

Generated: {datetime.now(timezone.utc).isoformat()}

## 章节一句话

待人工/AI 精读。本章开头信号：{first_sentences}

## 核心关键词

{", ".join(keywords) if keywords else "待提取"}

## 知识原子草稿

### Atom 1
- What / 观察现象：
- Mechanism / 底层机制：
- Plug-in Logic / 可复用逻辑：
- 可连接到 Creator 的哪个问题：

## 苏格拉底式追问

- 作者真正想解决的问题是什么？
- 这个观点依赖哪些隐含假设？
- 如果把这个观点放到 AI 时代育儿场景，会发生什么变化？
- Creator 会同意哪一部分，反驳哪一部分？
- 这个章节可以变成哪个长青选题？

## Creator 人工补充

> 我读完这一章最想保留的判断是：
"""


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "book"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("book_file")
    parser.add_argument("--title", help="Book title override.")
    parser.add_argument("--max-chapters", type=int, default=8)
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--chapter-chars", type=int, default=12000)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    path = Path(args.book_file).resolve()
    if not path.exists():
        raise SystemExit(f"Book file does not exist: {path}")
    book_title = args.title or path.stem
    chapters = split_chapters(read_book(path), args.max_chapters, args.min_chars)

    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_template = PROMPT_TEMPLATE.read_text(encoding="utf-8")

    for index, (chapter_title, body) in enumerate(chapters, 1):
        base = f"{slugify(book_title)}-ch{index:02d}-{slugify(chapter_title)}"
        chapter_path = CHAPTER_DIR / f"{base}.md"
        chapter_path.write_text(f"# {chapter_title}\n\n{body}", encoding="utf-8")

        prompt = f"""{prompt_template}

# Book

{book_title}

# Chapter

{chapter_title}

# Text

{body[: args.chapter_chars]}
"""
        prompt_path = PROMPT_DIR / f"{base}-prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        ai_output = "" if args.no_ai else call_openai(prompt, args.model)
        analysis = ai_output or heuristic_analysis(book_title, chapter_title, body)
        analysis_path = ANALYSIS_DIR / f"{base}-analysis.md"
        analysis_path.write_text(analysis, encoding="utf-8")
        print(f"Wrote chapter: {chapter_path}")
        print(f"Wrote analysis: {analysis_path}")
    print(f"Analyzed {len(chapters)} chapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

