import subprocess

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


def test_macos_security_fallback_reads_key_without_exposing_it(monkeypatch) -> None:
    def broken_keyring() -> InMemoryKeyring:
        raise RuntimeError("Keychain backend unavailable")

    monkeypatch.setattr(
        SystemKeyringSecretStore,
        "_keyring_module",
        staticmethod(broken_keyring),
    )
    monkeypatch.setattr("app.services.secret_store.sys.platform", "darwin")
    monkeypatch.setattr(
        SystemKeyringSecretStore,
        "_run_macos_security",
        staticmethod(
            lambda arguments: subprocess.CompletedProcess(
                arguments,
                0,
                stdout="user-owned-key\n",
                stderr="",
            )
        ),
    )

    assert SystemKeyringSecretStore().get_gemini_api_key() == "user-owned-key"
