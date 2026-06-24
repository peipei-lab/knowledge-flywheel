"""Local creator profile helpers.

The public repository keeps generic Creator wording. A local ignored
`config/brand_profile.local.json` can override the display name and lens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "brand_profile.json"
LOCAL_PROFILE = ROOT / "config" / "brand_profile.local.json"


def load_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {}
    for path in [DEFAULT_PROFILE, LOCAL_PROFILE]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            profile.update(data)
    return profile


def creator_name() -> str:
    return str(load_profile().get("name") or "Creator")


def feedback_dir_name() -> str:
    safe = "".join(ch for ch in creator_name() if ch.isalnum() or ch in "-_").strip()
    return f"30_{safe or 'Creator'}_Feedback"


def render_profile(text: str) -> str:
    profile = load_profile()
    name = str(profile.get("name") or "Creator")
    identity = str(profile.get("identity") or "")
    positioning = str(profile.get("positioning") or "")
    text = text.replace("Creator's", f"{name}'s")
    text = text.replace("Creator", name)
    if identity:
        text = text.replace("{{creator_identity}}", identity)
    if positioning:
        text = text.replace("{{creator_positioning}}", positioning)
    return text
