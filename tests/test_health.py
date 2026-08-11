from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.routers import pages


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_web_content_security_policy_disallows_eval(client: TestClient) -> None:
    response = client.get("/")

    assert "script-src 'self';" in response.headers["content-security-policy"]
    assert "'unsafe-eval'" not in response.headers["content-security-policy"]


def test_desktop_content_security_policy_allows_pywebview_bridge(
    client: TestClient,
) -> None:
    client.app.state.desktop_mode = True

    response = client.get("/")

    assert (
        "script-src 'self' 'unsafe-eval';"
        in response.headers["content-security-policy"]
    )


def test_cross_origin_mutation_is_rejected(client: TestClient) -> None:
    response = client.put(
        "/api/settings/gemini",
        headers={"Origin": "https://malicious.example"},
        json={"api_key": "private-test-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Запрос с внешнего сайта отклонён."


def test_main_page_is_available(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Interview Loom" in response.text
    assert "Скачать приложение" in response.text
    assert "/download/macos" in response.text
    assert "/download/windows" in response.text
    assert "Health-check" not in response.text
    assert ">API<" not in response.text
    assert "Разработка" not in response.text
    for label in ("Продукт", "Как это работает", "О проекте", "Поддержка", "Новая тренировка"):
        assert label in response.text


def test_support_page_is_available(client: TestClient) -> None:
    response = client.get("/support")

    assert response.status_code == 200
    assert "Где хранится мой Gemini API key?" in response.text
    assert "Контакт можно добавить сюда." in response.text


def test_macos_download_returns_built_package(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_path = tmp_path / "Interview-Loom-macOS-arm64.zip"
    package_path.write_bytes(b"test-package")
    monkeypatch.setattr(pages, "MACOS_PACKAGE_PATH", package_path)

    response = client.get("/download/macos")

    assert response.status_code == 200
    assert response.content == b"test-package"
    assert "Interview-Loom-macOS-arm64.zip" in response.headers["content-disposition"]


def test_macos_download_has_friendly_fallback(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pages, "MACOS_PACKAGE_PATH", tmp_path / "missing.zip")

    response = client.get("/download/macos")

    assert response.status_code == 404
    assert "Сборка ещё не готова" in response.text
