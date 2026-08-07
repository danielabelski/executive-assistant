#!/usr/bin/env bash
# dev.sh — the everyday commands, one short name each.
# Usage: scripts/dev.sh [test|doctor|briefing|wrapup|lint]
set -euo pipefail
cd "$(dirname "$0")/.."

cmd="${1:-help}"
case "$cmd" in
  test)     python -m pytest -q ;;
  doctor)   python -m executive_assistant doctor ;;
  briefing) python -m executive_assistant briefing ;;
  wrapup)   python -m executive_assistant wrapup ;;
  lint)     python -m py_compile executive_assistant/*.py && echo "compile ✓" ;;
  *) echo "usage: scripts/dev.sh [test|doctor|briefing|wrapup|lint]"; exit 1 ;;
esac
