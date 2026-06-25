#!/usr/bin/env python3
"""Promote raw feedback and curated choices into preference principles."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from profile_config import creator_name, feedback_dir_name


ROOT = Path(__file__).resolve().parents[1]
INSIGHT_VAULT = ROOT / "insight_vault"
RAW_VAULT = ROOT / "raw_capture_vault"
CONTENT = ROOT / "content"
FEEDBACK_DIR = INSIGHT_VAULT / feedback_dir_name()
RAW_EVENTS = FEEDBACK_DIR / "raw_feedback_events.jsonl"
PRINCIPLES_DIR = CONTENT / "knowledge" / "principles"
PREFERENCE_DIR = INSIGHT_VAULT / "40_Preference_Model"
REFLECTION_DIR = INSIGHT_VAULT / "45_Memory_Reflections"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_feedback_events(limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = sorted((INSIGHT_VAULT).glob("30_*_Feedback/raw_feedback_events.jsonl"))
    if RAW_EVENTS not in paths:
        paths.append(RAW_EVENTS)
    for path in paths:
        rows.extend(read_jsonl(path))
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    return rows[-limit:]


def clean(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"```", "```text", "text"}:
        return ""
    return text


def excerpt(value: object, limit: int = 180) -> str:
    text = clean(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def avg_score(event: dict[str, Any]) -> float:
    scores = event.get("scores") or {}
    values = [int(value) for value in scores.values() if isinstance(value, int)]
    return round(sum(values) / len(values), 2) if values else 0.0


def event_reward(event: dict[str, Any]) -> str:
    decision = str(event.get("decision") or "")
    avg = avg_score(event)
    if decision in {"keep", "publish", "deepen"} and avg >= 4:
        return "positive"
    if decision in {"skip", "archive"} or avg <= 2:
        return "negative"
    return "mixed"


def source_type_from_note(text: str) -> str:
    match = re.search(r"^Source type:\s*(.+)$", text, flags=re.M)
    return clean(match.group(1)).lower() if match else "unknown"


def section_after(text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    match = re.search(pattern, text, flags=re.M)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", text[start:], flags=re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def load_curated_notes(limit: int) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    for path in sorted((RAW_VAULT / "00_Inbox").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        if "Source priority: curated" not in text:
            continue
        title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        notes.append(
            {
                "title": title,
                "source_type": source_type_from_note(text),
                "why": section_after(text, "Why saved / user note") or section_after(text, "Why selected"),
                "path": str(path.relative_to(ROOT)),
            }
        )
    return notes[:limit]


def load_draft_feedback(limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    root = INSIGHT_VAULT / "70_Draft_Revisions"
    if not root.exists():
        return rows
    for path in sorted(root.rglob("v*-feedback.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if "_template" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "feedback": section_after(text, "Raw Feedback"),
                "rewrite": section_after(text, "Rewrite Instruction"),
            }
        )
    return rows[:limit]


def bullet_lines(items: list[str], empty: str = "- 暂无") -> str:
    unique = []
    for item in items:
        item = excerpt(item, 220)
        if item and item not in unique:
            unique.append(item)
    return "\n".join(f"- {item}" for item in unique) if unique else empty


def build_profiles(events: list[dict[str, Any]], curated: list[dict[str, str]], draft_feedback: list[dict[str, str]]) -> dict[str, str]:
    positive = [event for event in events if event_reward(event) == "positive"]
    negative = [event for event in events if event_reward(event) == "negative"]
    memory = [event for event in events if event.get("memory_candidate")]
    tag_counts = Counter(tag for event in events for tag in event.get("tags", []))
    decision_counts = Counter(str(event.get("decision") or "unknown") for event in events)
    source_counts = Counter(item["source_type"] for item in curated)

    selected_signals = [
        event.get("raw_feedback_text") or event.get("rewrite_instruction") or ",".join(event.get("tags", []))
        for event in positive + memory
    ]
    rejected_signals = [
        event.get("rejected_reason") or event.get("raw_feedback_text") or ",".join(event.get("tags", []))
        for event in negative
    ]
    source_signals = [f"{item['source_type']}: {item['why'] or item['title']}" for item in curated]
    revision_signals = [
        row["feedback"] or row["rewrite"]
        for row in draft_feedback
        if row.get("feedback") or row.get("rewrite")
    ]

    generated = now_iso()
    name = creator_name()

    taste_profile = f"""# Taste Profile

Generated: {generated}

## Decision Distribution

{bullet_lines([f"{key}: {value}" for key, value in decision_counts.most_common()])}

## Strong Positive Signals

{bullet_lines(selected_signals)}

## Avoid / Low-Signal Patterns

{bullet_lines(rejected_signals)}

## Raw Data Boundary

This file is distilled from immutable raw feedback events. Do not edit raw events; add new feedback through the review workflow.
"""

    voice_profile = f"""# Voice Profile

Generated: {generated}

## Draft Revision Signals

{bullet_lines(revision_signals)}

## Frequent Tags

{bullet_lines([f"{tag}: {count}" for tag, count in tag_counts.most_common(20)])}

## Working Hypothesis

{name}'s preferred voice should stay concrete, opinionated, human, and grounded in lived judgment. Treat this as provisional until more feedback accumulates.
"""

    source_quality = f"""# Source Quality Model

Generated: {generated}

## Curated Source Mix

{bullet_lines([f"{key}: {value}" for key, value in source_counts.most_common()])}

## Why Sources Were Selected

{bullet_lines(source_signals)}

## Current Rule

User-curated sources outrank AI-discovered sources unless repeated feedback marks them as low-signal.
"""

    axioms = f"""# Creator Principles And Axioms

Generated: {generated}

## Current Axioms

- Human curation is a high-value learning signal; preserve why a source was selected.
- Feedback text is training data; keep raw wording before summarizing it.
- Draft revisions reveal voice preference better than abstract style descriptions.
- Prefer sparse, relevant context over dumping the whole vault into every generation.
- Promote repeated feedback patterns into explicit writing and source-selection principles.

## Candidate New Principles From Recent Data

{bullet_lines(selected_signals[:8] + source_signals[:8] + revision_signals[:8])}

## Needs More Evidence

- Which source types consistently produce publishable ideas?
- Which draft structures survive review with minimal changes?
- Which topics create life-reflection value rather than just information value?
"""

    weekly_update = f"""# Weekly Preference Update

Generated: {generated}

## Inputs Reviewed

- Feedback events: {len(events)}
- Curated sources: {len(curated)}
- Draft feedback files: {len(draft_feedback)}

## What The System Should Remember

{bullet_lines(selected_signals[:6] + source_signals[:6] + revision_signals[:6])}

## What To Use Next Time

- Before drafting, retrieve only relevant principles, feedback events, and similar draft revisions.
- When ranking Materials, keep curated/high-priority sources visible.
- When writing Pages drafts, include the latest voice and taste profiles as compact context.
"""

    return {
        "taste_profile.md": taste_profile,
        "voice_profile.md": voice_profile,
        "source_quality.md": source_quality,
        "creator_axioms.md": axioms,
        "weekly_preference_update.md": weekly_update,
    }


def write_outputs(profiles: dict[str, str], date_label: str) -> list[Path]:
    PRINCIPLES_DIR.mkdir(parents=True, exist_ok=True)
    PREFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, text in profiles.items():
        if name == "weekly_preference_update.md":
            dated = REFLECTION_DIR / f"{date_label}-preference-update.md"
            dated.write_text(text, encoding="utf-8")
            content_dated = PRINCIPLES_DIR / f"{date_label}-preference-update.md"
            content_dated.write_text(text, encoding="utf-8")
            written.extend([dated, content_dated])
            continue
        pref_path = PREFERENCE_DIR / name
        pref_path.write_text(text, encoding="utf-8")
        content_path = PRINCIPLES_DIR / name
        content_path.write_text(text, encoding="utf-8")
        written.extend([pref_path, content_path])
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    events = load_feedback_events(args.limit)
    curated = load_curated_notes(args.limit)
    draft_feedback = load_draft_feedback(args.limit)
    profiles = build_profiles(events, curated, draft_feedback)
    written = write_outputs(profiles, args.date)
    for path in written:
        print(f"Wrote {path.relative_to(ROOT)}")
    print("Promoted feedback and curated choices into preference principles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
