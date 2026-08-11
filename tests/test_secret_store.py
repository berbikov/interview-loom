from app.services.secret_store import SystemKeyringSecretStore


class InMemoryKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        del self.values[(service_name, username)]


def test_system_keyring_key_survives_new_store_instance(monkeypatch) -> None:
    keyring = InMemoryKeyring()
    monkeypatch.setattr(
        SystemKeyringSecretStore,
        "_keyring_module",
        staticmethod(lambda: keyring),
    )

    SystemKeyringSecretStore().set_gemini_api_key(" user-key ")

    assert SystemKeyringSecretStore().get_gemini_api_key() == "user-key"

    SystemKeyringSecretStore().delete_gemini_api_key()
    assert SystemKeyringSecretStore().get_gemini_api_key() is None
