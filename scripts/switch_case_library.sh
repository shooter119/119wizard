#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_V1="$ROOT/data/fire_cases_complete.json"
SRC_V2="$ROOT/data/fire_cases_complete_v2.json"
BACKUP="$ROOT/data/fire_cases_complete.pre_v2.backup.json"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 use-v2|rollback"
  exit 1
fi

cmd="$1"

if [[ "$cmd" == "use-v2" ]]; then
  if [[ ! -f "$SRC_V2" ]]; then
    echo "Missing $SRC_V2"
    exit 1
  fi
  cp "$SRC_V1" "$BACKUP"
  cp "$SRC_V2" "$SRC_V1"
  echo "Switched to v2 case library. Backup saved to: $BACKUP"
elif [[ "$cmd" == "rollback" ]]; then
  if [[ ! -f "$BACKUP" ]]; then
    echo "Missing backup: $BACKUP"
    exit 1
  fi
  cp "$BACKUP" "$SRC_V1"
  echo "Rolled back to previous case library from: $BACKUP"
else
  echo "Unknown command: $cmd"
  echo "Usage: $0 use-v2|rollback"
  exit 1
fi
