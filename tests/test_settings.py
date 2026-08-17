from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import StubSecretStore


def test_gemini_key_can_be_saved_without_being_returned(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    response = client.put(
        "/api/settings/gemini",
        json={"api_key": "private-test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "editable": True,
        "storage": "test_keyring",
    }
    assert "private-test-key" not in response.text
    assert secret_store.api_key == "private-test-key"


def test_gemini_key_can_be_deleted(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    secret_store.api_key = "private-test-key"

    response = client.delete("/api/settings/gemini")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert secret_store.api_key is None


def test_invalid_gemini_key_is_not_saved(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    response = client.put(
        "/api/settings/gemini",
        json={"api_key": "invalid-test-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Gemini не принял API-ключ."
    assert secret_store.api_key is None


def test_gemini_key_can_be_checked_without_saving(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    response = client.post(
        "/api/settings/gemini/validate",
        json={"api_key": "private-test-key"},
    )

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert secret_store.api_key is None


def test_saved_gemini_key_can_be_checked_without_reentering_it(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    secret_store.api_key = "private-test-key"

    response = client.post("/api/settings/gemini/validate", json={})

    assert response.status_code == 200
    assert response.json()["configured"] is True


def test_settings_page_never_contains_saved_key(
    client: TestClient,
    secret_store: StubSecretStore,
) -> None:
    secret_store.api_key = "private-test-key"

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Gemini подключён" in response.text
    assert "private-test-key" not in response.text


def test_settings_key_field_is_a_native_password_input_without_paste_blocking(
    client: TestClient,
) -> None:
    client.app.state.desktop_mode = True

    response = client.get("/settings")
    script = (Path(__file__).parent.parent / "app" / "static" / "js" / "settings.js").read_text(
        encoding="utf-8"
    )

    assert 'id="gemini-api-key" type="password"' in response.text
    assert "onpaste" not in response.text.lower()
    assert "paste" not in script.lower()
