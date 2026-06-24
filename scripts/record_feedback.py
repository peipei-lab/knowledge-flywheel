#!/usr/bin/env python3
"""Append immutable Creator feedback events."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from profile_config import creator_name, feedback_dir_name


ROOT = Path(__file__).resolve().parents[1]
INSIGHT_VAULT = ROOT / "insight_vault"
FEEDBACK_DIR = INSIGHT_VAULT / feedback_dir_name()
RAW_EVENTS = FEEDBACK_DIR / "raw_feedback_events.jsonl"
FEEDBACK_LOG = FEEDBACK_DIR / "feedback_log.md"
REVIEW_INBOX = INSIGHT_VAULT / "60_Review_Inbox"
CANDIDATES_PATH = REVIEW_INBOX / "candidates.jsonl"
REVIEWED_IDS_PATH = REVIEW_INBOX / "reviewed_ids.json"
DRAFT_REVISIONS = INSIGHT_VAULT / "70_Draft_Revisions"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in value).strip().lower()
    return "-".join(safe.split())[:96] or "untitled"


def event_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def load_candidates() -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    if not CANDIDATES_PATH.exists():
        return candidates
    for line in CANDIDATES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates[str(item.get("candidate_id", ""))] = item
    return candidates


def read_reviewed_ids() -> list[str]:
    if not REVIEWED_IDS_PATH.exists():
        return []
    try:
        data = json.loads(REVIEWED_IDS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data] if isinstance(data, list) else []


def mark_reviewed(candidate_id: str) -> None:
    if not candidate_id:
        return
    ids = read_reviewed_ids()
    if candidate_id not in ids:
        ids.append(candidate_id)
    REVIEWED_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEWED_IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_scores(args: argparse.Namespace) -> dict[str, int]:
    return {
        "relevance": args.relevance,
        "insight": args.insight,
        "voice_match": args.voice_match,
        "publishability": args.publishability,
        "life_reflection_value": args.life_reflection_value,
    }


def normalize_tags(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，\n]+", value or "") if part.strip()]


def derived_dimensions(candidate: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    topics = candidate.get("topics") or []
    topic = " | ".join(str(item) for item in topics) if isinstance(topics, list) else str(topics)
    reward = "mixed"
    avg = sum(parse_scores(args).values()) / 5
    if args.decision in {"keep", "publish", "deepen"} and avg >= 4:
        reward = "positive"
    elif args.decision in {"skip", "archive"} or avg <= 2:
        reward = "negative"
    return {
        "topic": topic or "待判断",
        "voice_axis": args.voice_axis,
        "reward_signal": reward,
    }


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def append_feedback_log(event: dict[str, Any], candidate: dict[str, Any]) -> None:
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_LOG.exists():
        FEEDBACK_LOG.write_text(f"# {creator_name()} Feedback Log\n\n", encoding="utf-8")
    text = f"""
## {event['created_at']} - {candidate.get('title') or event.get('item_id')}

- Event ID: `{event['event_id']}`
- Feedback type: {event['feedback_type']}
- Item type: {event['item_type']}
- Source path: `{event.get('source_path', '')}`
- Decision: {event['decision']}
- Scores: {json.dumps(event['scores'], ensure_ascii=False)}
- Tags: {", ".join(event['tags']) if event['tags'] else "none"}
- Memory candidate: {event['memory_candidate']}

### Raw Feedback

{event['raw_feedback_text'] or "_No text feedback._"}

### Rewrite Instruction

{event.get('rewrite_instruction') or "_None_"}
"""
    with FEEDBACK_LOG.open("a", encoding="utf-8") as handle:
        handle.write(text)


def archive_draft(args: argparse.Namespace, event: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if args.feedback_type not in {"draft_review", "revision_feedback", "publish_decision"}:
        return {}

    article_slug = slugify(args.article_slug or candidate.get("title") or args.item_id or "draft")
    article_dir = DRAFT_REVISIONS / article_slug
    article_dir.mkdir(parents=True, exist_ok=True)
    version = f"v{args.revision_round:02d}"

    draft_before = ""
    draft_after = ""
    if args.draft_path_before:
        src = (ROOT / args.draft_path_before).resolve() if not Path(args.draft_path_before).is_absolute() else Path(args.draft_path_before)
        if src.exists():
            dest = article_dir / f"{version}-draft.md"
            shutil.copyfile(src, dest)
            draft_before = str(dest.relative_to(ROOT))
    if args.draft_path_after:
        src = (ROOT / args.draft_path_after).resolve() if not Path(args.draft_path_after).is_absolute() else Path(args.draft_path_after)
        if src.exists():
            dest = article_dir / f"{version}-after.md"
            shutil.copyfile(src, dest)
            draft_after = str(dest.relative_to(ROOT))

    feedback_path = article_dir / f"{version}-feedback.md"
    feedback_path.write_text(
        f"""# {version} Feedback

- Event ID: `{event['event_id']}`
- Decision: {event['decision']}
- Publish target: {args.publish_target}
- Approved for publish: {args.approved_for_publish}

## Blocking Issues

{chr(10).join(f"- {issue}" for issue in normalize_tags(args.blocking_issues)) or "- none"}

## Raw Feedback

{event['raw_feedback_text']}

## Rewrite Instruction

{event.get('rewrite_instruction') or "_None_"}
""",
        encoding="utf-8",
    )

    summary_path = article_dir / "revision_summary.md"
    if not summary_path.exists():
        summary_path.write_text(
            f"""# Revision Summary: {article_slug}

## Article

- Title: {candidate.get('title') or article_slug}
- Slug: {article_slug}
- Publish target: {args.publish_target}
- Final status: draft

## Version Timeline

| Version | Draft path | Feedback path | Decision | Main change |
|---|---|---|---|---|
""",
            encoding="utf-8",
        )
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {version} | {draft_before or args.draft_path_before or ''} | {feedback_path.relative_to(ROOT)} | {event['decision']} | {event.get('rewrite_instruction') or ''} |\n"
        )

    return {
        "publish_target": args.publish_target,
        "revision_round": args.revision_round,
        "draft_path_before": draft_before or args.draft_path_before,
        "draft_path_after": draft_after or args.draft_path_after,
        "blocking_issues": normalize_tags(args.blocking_issues),
        "requested_changes": [event["raw_feedback_text"]] if event["raw_feedback_text"] else [],
        "approved_for_publish": args.approved_for_publish,
        "revision_archive": str(article_dir.relative_to(ROOT)),
    }


def build_event(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = load_candidates()
    candidate = candidates.get(args.item_id, {})
    source_path = args.source_path or str(candidate.get("source_path", ""))
    event: dict[str, Any] = {
        "created_at": now_iso(),
        "item_id": args.item_id,
        "feedback_type": args.feedback_type,
        "item_type": args.item_type,
        "source_path": source_path,
        "source_url": args.source_url,
        "decision": args.decision,
        "scores": parse_scores(args),
        "tags": normalize_tags(args.tags),
        "raw_feedback_text": args.feedback_text,
        "selected_angle": args.selected_angle,
        "rejected_reason": args.rejected_reason,
        "rewrite_instruction": args.rewrite_instruction,
        "memory_candidate": args.memory_candidate,
        "derived_dimensions": derived_dimensions(candidate, args),
    }
    event["event_id"] = event_id(event)
    event["draft_review"] = archive_draft(args, event, candidate)
    return event, candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--feedback-type", default="quick_review")
    parser.add_argument("--item-type", default="analysis")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--decision", required=True, choices=["keep", "skip", "rewrite", "publish", "deepen", "archive"])
    parser.add_argument("--relevance", type=int, default=3)
    parser.add_argument("--insight", type=int, default=3)
    parser.add_argument("--voice-match", type=int, default=3)
    parser.add_argument("--publishability", type=int, default=3)
    parser.add_argument("--life-reflection-value", type=int, default=3)
    parser.add_argument("--tags", default="")
    parser.add_argument("--feedback-text", default="")
    parser.add_argument("--selected-angle", default="")
    parser.add_argument("--rejected-reason", default="")
    parser.add_argument("--rewrite-instruction", default="")
    parser.add_argument("--voice-axis", default="mixed")
    parser.add_argument("--memory-candidate", action="store_true")
    parser.add_argument("--article-slug", default="")
    parser.add_argument("--publish-target", default="")
    parser.add_argument("--revision-round", type=int, default=1)
    parser.add_argument("--draft-path-before", default="")
    parser.add_argument("--draft-path-after", default="")
    parser.add_argument("--blocking-issues", default="")
    parser.add_argument("--approved-for-publish", action="store_true")
    args = parser.parse_args()

    event, candidate = build_event(args)
    append_jsonl(RAW_EVENTS, event)
    append_feedback_log(event, candidate)
    mark_reviewed(args.item_id)
    print(f"Recorded feedback event: {event['event_id']}")
    print(f"Appended raw event: {RAW_EVENTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
