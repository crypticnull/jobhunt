#!/usr/bin/env bash
# Prefill today's session log from the day's commit subjects.
# 15 lines maximum after editing; dead ends stay in.
set -euo pipefail
dir="$(git rev-parse --show-toplevel)/docs/log"
mkdir -p "$dir"
last=$(ls "$dir" 2>/dev/null | grep -Eo '^[0-9]{4}' | sort | tail -1 || true)
next=$(printf '%04d' $((10#${last:-0} + 1)))
f="$dir/$next-$(date +%F).md"
{
  echo "# $(date +%F)"
  echo
  echo "Shipped:"
  git log --since=midnight --pretty='- %s'
  echo "Broke:"
  echo "Decided:"
  echo "Next:"
} > "$f"
echo "$f"
