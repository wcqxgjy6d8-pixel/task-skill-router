#!/usr/bin/env bash
# Linux installer entrypoint for task-skill-router.
set -euo pipefail

REPO="${TASK_SKILL_ROUTER_REPO:-${SKILL_ROUTER_REPO:-wcqxgjy6d8-pixel/task-skill-router}}"
REF="${TASK_SKILL_ROUTER_REF:-${SKILL_ROUTER_REF:-main}}"
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SOURCE_DIR=""
if [ -f "$SCRIPT_PATH" ]; then
    SOURCE_DIR="$(cd "$(dirname "$SCRIPT_PATH")" 2>/dev/null && pwd || true)"
fi

if [ "$(uname -s)" != "Linux" ]; then
    echo "Warning: this installer is labeled for Linux. Continuing anyway."
fi

if [ -n "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/install.sh" ]; then
    exec bash "$SOURCE_DIR/install.sh" "$@"
fi

if command -v curl >/dev/null 2>&1; then
    curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/install.sh" \
        | TASK_SKILL_ROUTER_REPO="$REPO" TASK_SKILL_ROUTER_REF="$REF" bash
elif command -v wget >/dev/null 2>&1; then
    wget -qO- "https://raw.githubusercontent.com/$REPO/$REF/install.sh" \
        | TASK_SKILL_ROUTER_REPO="$REPO" TASK_SKILL_ROUTER_REF="$REF" bash
else
    echo "Need curl or wget to download install.sh"
    exit 1
fi
