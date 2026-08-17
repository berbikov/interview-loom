import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "landing"
OUTPUT_DIR = ROOT / "public"
RELEASE_DIR = ROOT / "release"


def repository_slug() -> str:
    configured = os.environ.get("GITHUB_REPOSITORY", "local/interview-loom")
    return configured.strip().strip("/")


def template_values() -> dict[str, str]:
    slug = repository_slug()
    repository_url = f"https://github.com/{slug}"
    release_url = f"{repository_url}/releases/latest"
    release_tag = os.environ.get("WINDOWS_RELEASE_TAG", "v1.2.0").strip()
    has_local_macos_archive = (RELEASE_DIR / "Interview-Loom-macOS-arm64.zip").is_file()
    mac_download_url = os.environ.get("MAC_DOWNLOAD_URL")
    if not mac_download_url:
        mac_download_url = (
            "downloads/Interview-Loom-macOS-arm64.zip"
            if has_local_macos_archive
            else f"{release_url}/download/Interview-Loom-macOS-arm64.zip"
        )
    windows_download_url = (
        f"{repository_url}/releases/download/{release_tag}/Interview-Loom-Setup-x64.exe"
    )
    return {
        "{{SITE_URL}}": os.environ.get(
            "SITE_URL",
            "http://127.0.0.1:8000",
        ).rstrip("/"),
        "{{REPOSITORY_URL}}": repository_url,
        "{{RELEASE_URL}}": release_url,
        "{{MAC_DOWNLOAD_URL}}": mac_download_url,
        "{{WINDOWS_DOWNLOAD_URL}}": windows_download_url,
    }


def render(text: str, values: dict[str, str]) -> str:
    rendered = text
    for placeholder, value in values.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    values = template_values()

    index_template = (SOURCE_DIR / "index.template.html").read_text(encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(
        render(index_template, values),
        encoding="utf-8",
    )
    for filename in ("privacy.html", "support.html", "terms.html"):
        source = (SOURCE_DIR / filename).read_text(encoding="utf-8")
        (OUTPUT_DIR / filename).write_text(render(source, values), encoding="utf-8")
    for filename in ("styles.css", "legal.css", "_headers"):
        shutil.copy2(SOURCE_DIR / filename, OUTPUT_DIR / filename)
    shutil.copy2(ROOT / "assets" / "app-icon.png", OUTPUT_DIR / "app-icon.png")
    downloads_dir = OUTPUT_DIR / "downloads"
    mac_release_files = (
        "Interview-Loom-macOS-arm64.zip",
        "Interview-Loom-macOS-arm64.sha256",
        "Interview-Loom-macOS-arm64.manifest.json",
    )
    if all((RELEASE_DIR / filename).is_file() for filename in mac_release_files):
        downloads_dir.mkdir()
        for filename in mac_release_files:
            shutil.copy2(RELEASE_DIR / filename, downloads_dir / filename)
    custom_domain = os.environ.get("CUSTOM_DOMAIN", "").strip()
    if custom_domain:
        (OUTPUT_DIR / "CNAME").write_text(custom_domain + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
