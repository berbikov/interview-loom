from pathlib import Path

from scripts.build_landing import render, template_values
from scripts.verify_landing import verify_landing


def test_landing_template_values_use_repository_release(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/interview-loom")
    monkeypatch.setenv("SITE_URL", "https://interview.example")

    values = template_values()
    rendered = render(
        "{{SITE_URL}} {{MAC_DOWNLOAD_URL}} {{WINDOWS_DOWNLOAD_URL}}",
        values,
    )

    assert "{{" not in rendered
    assert "https://interview.example" in rendered
    assert "downloads/Interview-Loom-macOS-arm64.zip" in rendered
    assert "Interview-Loom-macOS-arm64.zip" in rendered
    assert (
        "https://github.com/example/interview-loom/releases/download/v1.2.0/"
        "Interview-Loom-Setup-x64.exe"
    ) in rendered


def test_landing_verifier_supports_github_pages_subpath(tmp_path) -> None:
    (tmp_path / "styles.css").write_text("body{}", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<link rel="stylesheet" href="styles.css"><a href="privacy.html">OK</a>',
        encoding="utf-8",
    )
    (tmp_path / "privacy.html").write_text(
        '<a href="./">На главную</a>',
        encoding="utf-8",
    )

    assert verify_landing(tmp_path) == []


def test_landing_verifier_rejects_root_relative_asset(tmp_path) -> None:
    (tmp_path / "index.html").write_text(
        '<link rel="stylesheet" href="/styles.css">',
        encoding="utf-8",
    )

    errors = verify_landing(tmp_path)

    assert len(errors) == 1
    assert "GitHub Pages subpath" in errors[0]


def test_landing_describes_existing_ai_chat_and_support() -> None:
    template = (Path(__file__).parent.parent / "landing" / "index.template.html").read_text(
        encoding="utf-8"
    )

    assert "Диалог" in template
    assert "В разработке" not in template
    assert 'href="support.html"' in template
