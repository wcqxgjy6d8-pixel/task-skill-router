#!/usr/bin/env bash
# task-skill-router installer - one-line setup
set -euo pipefail

REPO="${TASK_SKILL_ROUTER_REPO:-${SKILL_ROUTER_REPO:-}}"
REF="${TASK_SKILL_ROUTER_REF:-${SKILL_ROUTER_REF:-main}}"
INSTALL_DIR="${TASK_SKILL_ROUTER_HOME:-${SKILL_ROUTER_HOME:-$HOME/.task-skill-router}}"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/task-skill-router"
BIN_DIR="$HOME/.local/bin"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "$REPO" ]; then
    echo "Installing task-skill-router from $REPO@$REF"
else
    echo "Installing task-skill-router from $SOURCE_DIR"
fi

# Create directories
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$BIN_DIR"

download() {
    local url="$1"
    local dest="$2"
    if command -v curl &>/dev/null; then
        curl -fsSL "$url" -o "$dest"
    elif command -v wget &>/dev/null; then
        wget -q "$url" -O "$dest"
    else
        echo "Need curl or wget to download"
        exit 1
    fi
}

install_file() {
    local rel="$1"
    local dest="$2"
    if [ -n "$REPO" ]; then
        download "https://raw.githubusercontent.com/$REPO/$REF/$rel" "$dest"
    else
        cp "$SOURCE_DIR/$rel" "$dest"
    fi
}

install_file "task-skill-router.py" "$INSTALL_DIR/task-skill-router.py"

if python3 - <<'PY' 2>/dev/null
import yaml
PY
then
    :
else
    echo "PyYAML is not installed. The router will use its built-in limited YAML parser."
    echo "For full YAML support, run: python3 -m pip install PyYAML"
fi

chmod +x "$INSTALL_DIR/task-skill-router.py"
ln -sf "$INSTALL_DIR/task-skill-router.py" "$BIN_DIR/task-skill-router"
ln -sf "$INSTALL_DIR/task-skill-router.py" "$BIN_DIR/task-skill-router.py"
# Compatibility with early prototypes.
ln -sf "$INSTALL_DIR/task-skill-router.py" "$BIN_DIR/skill-router.py"

# Copy default config (don't overwrite existing)
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    install_file "config/config.yaml" "$CONFIG_DIR/config.yaml"
    echo "Created $CONFIG_DIR/config.yaml"
fi

# Copy community mapping (don't overwrite)
if [ ! -f "$CONFIG_DIR/community.yaml" ]; then
    install_file "config/community.yaml" "$CONFIG_DIR/community.yaml"
    echo "Created $CONFIG_DIR/community.yaml"
fi

# Check PATH
case ":$PATH:" in
    *:$BIN_DIR:*) ;;
    *)
        echo "Add $BIN_DIR to your PATH:"
        echo "   export PATH=\"\$PATH:$BIN_DIR\""
        ;;
esac

echo ""
echo "task-skill-router installed."
echo ""
echo "   Try it:"
echo "   task-skill-router \"fix a bug in my auth module\""
echo ""
echo "   Configure: $CONFIG_DIR/config.yaml"
echo "   Community: $CONFIG_DIR/community.yaml"
