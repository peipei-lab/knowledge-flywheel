#!/usr/bin/env python3
"""Fetch curated RSS/Atom sources into a dated local inbox."""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "sources.json"
INBOX = ROOT / "content" / "inbox"
STATE = ROOT / "content" / "state" / "seen.json"


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except Exception:
        return clean_text(value)


def node_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text
    for child in node:
        local = child.tag.split("}")[-1]
        if local in names and child.text:
            return child.text
    return ""


def node_link(node: ET.Element) -> str:
    rss_link = node_text(node, ["link"])
    if rss_link:
        return clean_text(rss_link)
    for child in node:
        local = child.tag.split("}")[-1]
        if local == "link" and child.attrib.get("href"):
            return child.attrib["href"]
    return ""


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CreatorBrandFactory/0.1 (+local personal workflow)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_feed(xml_bytes: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        # Some publisher feeds occasionally emit bare ampersands in text fields.
        repaired = re.sub(rb"&(?!#?[a-zA-Z0-9]+;)", b"&amp;", xml_bytes)
        root = ET.fromstring(repaired)
    channel_items = root.findall("./channel/item")
    atom_entries = [n for n in root.findall("{http://www.w3.org/2005/Atom}entry")]
    nodes = channel_items or atom_entries
    items: list[dict[str, Any]] = []
    for node in nodes:
        title = clean_text(node_text(node, ["title"]))
        link = node_link(node)
        guid = clean_text(node_text(node, ["guid", "id"])) or link or title
        published_raw = node_text(node, ["pubDate", "published", "updated"])
        summary = clean_text(node_text(node, ["description", "summary", "content"]))
        stable_id = hashlib.sha256(f"{source['id']}|{guid}".encode()).hexdigest()[:16]
        items.append(
            {
                "id": stable_id,
                "source_id": source["id"],
                "source_name": source["name"],
                "source_angle": source.get("angle", ""),
                "priority": source.get("priority", 3),
                "title": title,
                "url": link,
                "published": parse_date(published_raw),
                "summary": summary,
            }
        )
    return items


def load_seen() -> set[str]:
    if not STATE.exists():
        return set()
    return set(json.loads(STATE.read_text(encoding="utf-8")))


def save_seen(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def within_window(item: dict[str, Any], days_back: int) -> bool:
    if not item.get("published"):
        return True
    try:
        published = datetime.fromisoformat(item["published"]).date()
    except ValueError:
        return True
    return published >= (datetime.now(timezone.utc).date() - timedelta(days=days_back))


def write_markdown(item: dict[str, Any], out_dir: Path) -> None:
    path = out_dir / f"{item['id']}.md"
    body = f"""# {item['title']}

- Source: {item['source_name']}
- Published: {item['published'] or 'unknown'}
- URL: {item['url']}
- Source angle: {item['source_angle']}

## Feed Summary

{item['summary'] or '_No summary provided in feed._'}

## Manual Transcript / Notes

Paste transcript excerpts, your listening notes, or article highlights here if needed.
"""
    path.write_text(body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-seen", action="store_true", help="Include items already fetched before.")
    parser.add_argument("--date", default=datetime.now().date().isoformat(), help="Inbox date, YYYY-MM-DD.")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    out_dir = INBOX / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    seen = load_seen()
    collected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    days_back = int(config.get("days_back", 14))
    limit = int(config.get("run_limit_per_source", 3))

    for source in sorted(config["sources"], key=lambda s: s.get("priority", 99)):
        try:
            items = parse_feed(fetch(source["url"]), source)
            fresh = [i for i in items if within_window(i, days_back)]
            if not args.include_seen:
                fresh = [i for i in fresh if i["id"] not in seen]
            for item in fresh[:limit]:
                write_markdown(item, out_dir)
                collected.append(item)
                seen.add(item["id"])
        except Exception as exc:
            errors.append({"source": source["name"], "error": str(exc)})

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": collected,
        "errors": errors,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    save_seen(seen)
    print(f"Fetched {len(collected)} new items into {out_dir}")
    if errors:
        print("Errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error['source']}: {error['error']}", file=sys.stderr)
    return 0 if collected or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
