#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    PYTHON_BIN="$(command -v python)"
fi
APP_PATH="$PROJECT_DIR/dist/Interview Loom.app"
RELEASE_DIR="$PROJECT_DIR/release"
ZIP_PATH="$RELEASE_DIR/Interview-Loom-macOS-arm64.zip"
DMG_PATH="$RELEASE_DIR/Interview-Loom-macOS-arm64.dmg"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Сборка macOS поддерживается только на macOS."
    exit 1
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "Не найден Python для сборки."
    exit 1
fi

mkdir -p "$RELEASE_DIR"
cd "$PROJECT_DIR"

"$PYTHON_BIN" scripts/generate_icons.py
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm interview_loom.spec

if [[ ! -d "$APP_PATH" ]]; then
    echo "PyInstaller не создал Interview Loom.app."
    exit 1
fi

if [[ -n "${MACOS_SIGNING_IDENTITY:-}" ]]; then
    codesign --force --deep --options runtime --timestamp \
        --sign "$MACOS_SIGNING_IDENTITY" "$APP_PATH"
    codesign --verify --deep --strict --verbose=2 "$APP_PATH"
else
    echo "MACOS_SIGNING_IDENTITY не задан: создаётся неподписанная beta-сборка."
fi

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

if hdiutil create \
    -volname "Interview Loom" \
    -srcfolder "$APP_PATH" \
    -format UDZO \
    -ov \
    "$DMG_PATH"; then
    echo "Создано: $DMG_PATH"
else
    echo "DMG недоступен; ZIP остаётся готовым артефактом."
fi

echo "Создано: $ZIP_PATH"
