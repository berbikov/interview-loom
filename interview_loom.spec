# ruff: noqa: F821

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

from app.metadata import APP_IDENTIFIER, APP_NAME, APP_VERSION

ROOT = Path.cwd()
APPLICATION_NAME = APP_NAME
DATA_FILES = [
    (str(ROOT / "app" / "templates"), "app/templates"),
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "migrations"), "migrations"),
    (str(ROOT / "alembic.ini"), "."),
]
BINARIES = []
HIDDEN_IMPORTS = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "keyring.backends.macOS",
    "keyring.backends.Windows",
]

for package_name in (
    "av",
    "charset_normalizer",
    "cryptography",
    "ctranslate2",
    "faster_whisper",
    "google.auth",
    "google.genai",
    "keyring",
    "onnxruntime",
    "requests",
    "tokenizers",
    "webview",
):
    package_data, package_binaries, package_imports = collect_all(package_name)
    DATA_FILES.extend(package_data)
    BINARIES.extend(package_binaries)
    HIDDEN_IMPORTS.extend(package_imports)

HIDDEN_IMPORTS.extend(collect_submodules("sqlalchemy.dialects.sqlite"))

analysis = Analysis(
    [str(ROOT / "desktop" / "main.py")],
    pathex=[str(ROOT)],
    binaries=BINARIES,
    datas=DATA_FILES,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=1,
)
python_archive = PYZ(analysis.pure)
executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APPLICATION_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / ("app-icon.ico" if sys.platform == "win32" else "app-icon.icns")),
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name=APPLICATION_NAME,
)

if sys.platform == "darwin":
    application = BUNDLE(
        collection,
        name=f"{APPLICATION_NAME}.app",
        icon=str(ROOT / "assets" / "app-icon.icns"),
        bundle_identifier=APP_IDENTIFIER,
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": "1",
            "LSMinimumSystemVersion": "12.0",
            "NSCameraUsageDescription": "Камера нужна для записи тренировочного интервью.",
            "NSMicrophoneUsageDescription": (
                "Микрофон нужен для записи ответа на тренировочном интервью."
            ),
            "NSScreenCaptureUsageDescription": "Доступ к экрану нужен для записи демонстрации.",
        },
    )
