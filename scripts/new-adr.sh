#!/usr/bin/env bash
# Stamp the next ADR number and template. Usage: scripts/new-adr.sh "short title"
set -euo pipefail
[ -n "${1:-}" ] || { echo "usage: $0 \"short title\"" >&2; exit 1; }
dir="$(git rev-parse --show-toplevel)/docs/decisions"
last=$(ls "$dir" 2>/dev/null | grep -Eo '^[0-9]{4}' | sort | tail -1 || true)
next=$(printf '%04d' $((10#${last:-0} + 1)))
slug=$(echo "$1" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
f="$dir/$next-$slug.md"
cat > "$f" <<EOF
# $next: $1

Date: $(date +%F)
Status: accepted

## Context

## Decision

## Tradeoff accepted
EOF
echo "$f"
