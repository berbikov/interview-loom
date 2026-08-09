#!/usr/bin/env bash
set -euo pipefail

CONTENTS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PYTHON_DIR="$RESOURCES_DIR/python"

export PYTHONHOME="$PYTHON_DIR"
export PYTHONPATH="$PYTHON_DIR/lib/python3.12/site-packages:$RESOURCES_DIR"
export RESOURCEPATH="$RESOURCES_DIR"

exec "$PYTHON_DIR/bin/python3.12" "$RESOURCES_DIR/desktop/main.py" "$@"
