#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE_LABEL="${1:-$(date +%F)}"

python3 "$ROOT/scripts/fetch_rss.py" --date "$DATE_LABEL"
python3 "$ROOT/scripts/build_brief.py" "$ROOT/content/inbox/$DATE_LABEL"
python3 "$ROOT/scripts/make_social.py" "$ROOT/content/briefs/$DATE_LABEL-weekly-brief.md"
python3 "$ROOT/scripts/build_knowledge_base.py" "$ROOT/content/briefs/$DATE_LABEL-weekly-brief.md"
python3 "$ROOT/scripts/weekly_reflection.py" "$DATE_LABEL"
python3 "$ROOT/scripts/promote_principles.py" --date "$DATE_LABEL"
python3 "$ROOT/scripts/sync_obsidian.py" --date "$DATE_LABEL"

echo
echo "Done. Review these files:"
echo "- $ROOT/content/briefs/$DATE_LABEL-weekly-brief.md"
echo "- $ROOT/content/social/$DATE_LABEL-xiaohongshu.md"
echo "- $ROOT/content/social/$DATE_LABEL-twitter-thread.md"
echo "- $ROOT/content/social/$DATE_LABEL-video-outline.md"
echo "- $ROOT/content/knowledge/atoms/$DATE_LABEL-knowledge-atoms.md"
echo "- $ROOT/content/knowledge/reflections/$DATE_LABEL-cognitive-reflection.md"
echo "- $ROOT/content/knowledge/principles/$DATE_LABEL-preference-update.md"
echo "- $ROOT/obsidian_vault/Home.md"
