#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
BUILD_ROOT="$PROJECT_DIR/.build/portable-macos"
APP_PATH="$BUILD_ROOT/Interview Loom.app"
CONTENTS_DIR="$APP_PATH/Contents"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PYTHON_DIR="$RESOURCES_DIR/python"
RELEASE_DIR="$PROJECT_DIR/release"
ZIP_PATH="$RELEASE_DIR/Interview-Loom-macOS-arm64.zip"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Portable macOS build is only available on macOS."
    exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Missing .venv. Install requirements-build.txt first."
    exit 1
fi

BASE_PREFIX="$($PYTHON_BIN -c 'import sys; print(sys.base_prefix)')"
VENV_SITE_PACKAGES="$($PYTHON_BIN -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"

rm -rf "$BUILD_ROOT"
mkdir -p "$CONTENTS_DIR/MacOS" "$RESOURCES_DIR" "$RELEASE_DIR"

cp -R "$BASE_PREFIX" "$PYTHON_DIR"
mkdir -p "$PYTHON_DIR/lib/python3.12/site-packages"
cp -R "$VENV_SITE_PACKAGES/." "$PYTHON_DIR/lib/python3.12/site-packages/"
cp -R "$PROJECT_DIR/app" "$RESOURCES_DIR/app"
cp -R "$PROJECT_DIR/desktop" "$RESOURCES_DIR/desktop"
cp -R "$PROJECT_DIR/migrations" "$RESOURCES_DIR/migrations"
cp -R "$PROJECT_DIR/assets" "$RESOURCES_DIR/assets"
cp "$PROJECT_DIR/alembic.ini" "$RESOURCES_DIR/alembic.ini"
cp "$PROJECT_DIR/desktop/macos/Info.plist" "$CONTENTS_DIR/Info.plist"
APP_VERSION="$($PYTHON_BIN -c 'from app.metadata import APP_VERSION; print(APP_VERSION)')"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$CONTENTS_DIR/Info.plist"
cp "$PROJECT_DIR/desktop/macos/launcher.sh" "$CONTENTS_DIR/MacOS/Interview Loom"
chmod +x "$CONTENTS_DIR/MacOS/Interview Loom"

find "$APP_PATH" -type d \( -name __pycache__ -o -name tests \) -prune -exec rm -rf {} +
find "$APP_PATH" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

"$CONTENTS_DIR/MacOS/Interview Loom" --smoke-test
rm -f "$ZIP_PATH"
cd "$BUILD_ROOT"
/usr/bin/zip -q -r -9 -y "$ZIP_PATH" "Interview Loom.app" \
    -x '*.dSYM/*' '*__pycache__/*' '*.pyc' '*.pyo' '*.pyi' \
    '*site-packages/artifact_tool_v2/*' '*site-packages/pandas/*' \
    '*site-packages/pandas-*.dist-info/*' '*site-packages/lxml/*' \
    '*site-packages/lxml-*.dist-info/*' '*site-packages/mypy/*' \
    '*site-packages/mypyc/*' '*site-packages/mypy-*.dist-info/*' \
    '*0aca9ce3d91742c5b361__mypyc*' '*site-packages/PIL/*' \
    '*site-packages/pillow-*.dist-info/*' '*site-packages/PyObjCTest/*' \
    '*site-packages/pdfminer/*' '*site-packages/pdfminer*.dist-info/*' \
    '*site-packages/pypdfium2*' '*site-packages/reportlab/*' \
    '*site-packages/reportlab-*.dist-info/*' '*site-packages/PyInstaller/*' \
    '*site-packages/pyinstaller*.dist-info/*' \
    '*site-packages/_pyinstaller_hooks_contrib/*' '*site-packages/py2app/*' \
    '*site-packages/py2app-*.dist-info/*' '*site-packages/modulegraph/*' \
    '*site-packages/macholib/*' '*site-packages/altgraph/*' \
    '*site-packages/setuptools/*' '*site-packages/setuptools-*.dist-info/*' \
    '*site-packages/pip/*' '*site-packages/pip-*.dist-info/*' \
    '*site-packages/pygments/*' '*site-packages/pygments-*.dist-info/*' \
    '*site-packages/docx/*' '*site-packages/python_docx-*.dist-info/*' \
    '*site-packages/pptx/*' '*site-packages/python_pptx-*.dist-info/*' \
    '*site-packages/openpyxl/*' '*site-packages/openpyxl-*.dist-info/*' \
    '*site-packages/xlsxwriter/*' '*site-packages/XlsxWriter-*.dist-info/*' \
    '*site-packages/_pytest/*' '*site-packages/pytest-*.dist-info/*' \
    '*site-packages/httpx2/*' '*site-packages/httpx2-*.dist-info/*' \
    '*site-packages/ruff*' '*site-packages/pathspec/*' \
    '*site-packages/iniconfig/*' '*site-packages/pluggy/*' \
    '*site-packages/pypdf/*' '*site-packages/pypdf-*.dist-info/*' \
    '*site-packages/pdfplumber/*' '*site-packages/pdfplumber-*.dist-info/*'

echo "Created portable beta: $ZIP_PATH"
