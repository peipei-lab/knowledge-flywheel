#!/usr/bin/env python3
"""Build a HITL review inbox from analysis notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSIGHT_VAULT = ROOT / "insight_vault"
ANALYSES_DIR = INSIGHT_VAULT / "10_Analyses"
INBOX_DIR = INSIGHT_VAULT / "60_Review_Inbox"
CANDIDATES_PATH = INBOX_DIR / "candidates.jsonl"
INDEX_PATH = INBOX_DIR / "review_inbox.md"
REVIEWED_IDS_PATH = INBOX_DIR / "reviewed_ids.json"
TEST_MARKERS = [
    "test",
    "demo",
    "sample",
    "structured-test",
    "score-test",
    "live-final",
    "final-ui-test",
    "auto-sync-test",
    "no-sync-test",
    "ui-test",
    "2026-06-23-huaren-candidates",
]


KEYWORDS = {
    "creator_fit": ["AI", "孩子", "妈妈", "女性", "职业", "育儿", "学习", "人生", "选择", "成长"],
    "mechanism_value": ["机制", "底层", "判断", "系统", "模型", "反馈", "闭环", "认知", "训练"],
    "emotional_density": ["焦虑", "困惑", "真实", "痛点", "争论", "不同意", "觉得", "担心"],
    "reusability": ["知识原子", "可复用", "长青", "选题", "视频", "小红书", "文章"],
    "novelty": ["不是", "误区", "错了", "反直觉", "真正", "稀缺", "新"],
    "contradiction_value": ["矛盾", "冲突", "反驳", "不同", "但是", "不过", "争论"],
    "life_reflection_value": ["人生", "选择", "不确定", "自我", "长期", "成长", "主体性", "意义"],
}

WEIGHTS = {
    "creator_fit": 0.22,
    "mechanism_value": 0.20,
    "emotional_density": 0.15,
    "reusability": 0.15,
    "novelty": 0.10,
    "contradiction_value": 0.10,
    "life_reflection_value": 0.05,
    "source_quality": 0.03,
}


def clean_text(value: str) -> str:
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def excerpt(value: str, limit: int = 420) -> str:
    flat = re.sub(r"\s+", " ", value).strip()
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "..."


def stable_id(path: Path, title: str) -> str:
    raw = f"{path.relative_to(ROOT)}::{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def read_reviewed_ids() -> set[str]:
    if not REVIEWED_IDS_PATH.exists():
        return set()
    try:
        data = json.loads(REVIEWED_IDS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line.strip("# ").strip()
    return fallback


def section_after(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", text[start:], re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def first_section_after(text: str, headings: list[str]) -> str:
    for heading in headings:
        section = section_after(text, heading)
        if section:
            return section
    return ""


def first_perspective_section(text: str) -> str:
    explicit = first_section_after(text, ["Creator 视角"])
    if explicit:
        return explicit
    pattern = re.compile(r"^##\s+.+视角\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", text[start:], re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def first_bullet(section: str) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            return stripped[2:].strip()
    return excerpt(section, 160)


def content_topics(text: str) -> list[str]:
    topics: list[str] = []
    checks = [
        ("AI x 育儿", ["孩子", "育儿", "学习", "编程"]),
        ("AI x 女性职业", ["女性", "职业", "职场", "工作"]),
        ("AI x 人生思考", ["人生", "选择", "长期", "成长", "主体性"]),
        ("AI x 知识管理", ["知识库", "第二大脑", "知识原子", "Obsidian"]),
    ]
    for label, words in checks:
        if any(word in text for word in words):
            topics.append(label)
    return topics or ["待判断"]


def score_dimension(text: str, dimension: str) -> float:
    words = KEYWORDS[dimension]
    hits = sum(1 for word in words if word.lower() in text.lower())
    return min(5.0, hits * 1.25)


def score_candidate(text: str) -> tuple[float, dict[str, float]]:
    dimensions = {name: score_dimension(text, name) for name in KEYWORDS}
    dimensions["source_quality"] = 3.0
    weighted = sum(dimensions[name] * weight for name, weight in WEIGHTS.items())
    return round(weighted, 3), {name: round(value, 2) for name, value in dimensions.items()}


def extract_candidates(path: Path) -> list[dict[str, Any]]:
    text = clean_text(path.read_text(encoding="utf-8"))
    title = markdown_title(text, path.stem)
    source_file = ""
    source_match = re.search(r"^Source file:\s*(.+)$", text, re.M)
    if source_match:
        source_file = source_match.group(1).strip()

    core = first_perspective_section(text) or section_after(text, "自动结论草稿") or excerpt(text, 900)
    mechanism = section_after(text, "Mechanism / 底层机制")
    what = section_after(text, "What / 观察现象")
    topics = section_after(text, "内容选题")
    recommended_angle = first_bullet(topics) if topics else ""
    body_for_scoring = "\n".join([title, core, mechanism, what, topics, text[:2000]])
    total_score, scores = score_candidate(body_for_scoring)

    candidate = {
        "candidate_id": stable_id(path, title),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "source_path": str(path.relative_to(ROOT)),
        "source_file": source_file,
        "source_type": infer_source_type(path, text),
        "summary": excerpt(core or what or text, 520),
        "mechanism": excerpt(mechanism, 520),
        "recommended_angle": recommended_angle,
        "topics": content_topics(body_for_scoring),
        "score": total_score,
        "scores": scores,
        "status": "pending",
    }
    return [candidate]


def is_test_candidate(path: Path, candidate: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            path.name,
            str(candidate.get("title", "")),
            str(candidate.get("source_path", "")),
            str(candidate.get("source_file", "")),
        ]
    ).lower()
    return any(marker in haystack for marker in TEST_MARKERS)


def infer_source_type(path: Path, text: str) -> str:
    lower = f"{path.name}\n{text[:1000]}".lower()
    if "xiaohongshu" in lower or "小红书" in lower:
        return "xiaohongshu"
    if "huaren" in lower:
        return "huaren"
    if "book" in lower or "chapter" in lower:
        return "book"
    return "analysis"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def write_index(candidates: list[dict[str, Any]]) -> None:
    rows = []
    for index, item in enumerate(candidates, 1):
        rows.append(
            f"""## {index}. {item['title']}

- Candidate ID: `{item['candidate_id']}`
- Score: {item['score']}
- Source type: {item['source_type']}
- Topics: {", ".join(item['topics'])}
- Source path: `{item['source_path']}`
- Recommended angle: {item['recommended_angle'] or "待判断"}

### Summary

{item['summary']}

### Scores

{json.dumps(item['scores'], ensure_ascii=False)}
"""
        )

    body = f"""# Review Inbox

Generated: {datetime.now(timezone.utc).isoformat()}

Pending candidates: {len(candidates)}

{chr(10).join(rows) if rows else "_No pending candidates._"}
"""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--include-reviewed", action="store_true")
    parser.add_argument("--include-test", action="store_true", help="Include test/demo/sample candidates.")
    args = parser.parse_args()

    reviewed_ids = set() if args.include_reviewed else read_reviewed_ids()
    candidates: list[dict[str, Any]] = []
    for path in sorted(ANALYSES_DIR.glob("*.md")):
        for candidate in extract_candidates(path):
            if not args.include_test and is_test_candidate(path, candidate):
                continue
            if candidate["candidate_id"] not in reviewed_ids:
                candidates.append(candidate)

    candidates.sort(key=lambda item: (-float(item["score"]), item["title"]))
    candidates = candidates[: args.limit]
    write_jsonl(CANDIDATES_PATH, candidates)
    write_index(candidates)
    print(f"Wrote review candidates: {CANDIDATES_PATH}")
    print(f"Wrote review inbox index: {INDEX_PATH}")
    print(f"Pending candidates: {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
