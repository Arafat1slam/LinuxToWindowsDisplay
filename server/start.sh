#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 &> /dev/null; then
    echo "python3 is not installed"
    exit 1
fi

if ! command -v gst-inspect-1.0 &> /dev/null; then
    echo "GStreamer tools not found (gst-inspect-1.0)"
    echo "Please see DEVELOPMENT.md §2 for installation instructions."
    exit 1
fi

if ! groups | grep -qw "input"; then
    echo "Error: user is not in 'input' group. uinput will fail."
    echo "Please see DEVELOPMENT.md §2 for instructions on adding your user to the input group."
    exit 1
fi

VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
HASH_FILE="$VENV_DIR/.requirements_hash"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

CURRENT_HASH=$(sha256sum "$REQ_FILE" | awk '{print $1}')
STORED_HASH=""
if [ -f "$HASH_FILE" ]; then
    STORED_HASH=$(cat "$HASH_FILE")
fi

if [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
    echo "Installing/updating requirements..."
    "$VENV_DIR/bin/pip" install -r "$REQ_FILE"
    echo "$CURRENT_HASH" > "$HASH_FILE"
fi

export PYTHONPATH="$SCRIPT_DIR/../common"

exec "$VENV_DIR/bin/python3" -m screenlink_server "$@"
