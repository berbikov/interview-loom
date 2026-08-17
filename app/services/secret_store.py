import logging
import subprocess
import sys
from typing import Protocol, cast

from app.config import Settings

logger = logging.getLogger(__name__)
GEMINI_KEY_SERVICE = "Interview Loom"
GEMINI_KEY_USERNAME = "gemini-api-key"


class SecretStoreError(RuntimeError):
    pass


class SecretStoreProtocol(Protocol):
    @property
    def storage_name(self) -> str: ...

    @property
    def is_editable(self) -> bool: ...

    def get_gemini_api_key(self) -> str | None: ...

    def set_gemini_api_key(self, api_key: str) -> None: ...

    def delete_gemini_api_key(self) -> None: ...


class KeyringModuleProtocol(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class EnvironmentSecretStore:
    """Read-only secret source used by the web/server process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def storage_name(self) -> str:
        return "environment"

    @property
    def is_editable(self) -> bool:
        return False

    def get_gemini_api_key(self) -> str | None:
        return self.settings.resolved_gemini_api_key

    def set_gemini_api_key(self, api_key: str) -> None:
        raise SecretStoreError(
            "В веб-режиме ключ настраивается только через переменную окружения."
        )

    def delete_gemini_api_key(self) -> None:
        raise SecretStoreError(
            "В веб-режиме ключ настраивается только через переменную окружения."
        )


class SystemKeyringSecretStore:
    """Stores a desktop user's Gemini key in the operating-system credential vault."""

    @property
    def storage_name(self) -> str:
        return "system_keyring"

    @property
    def is_editable(self) -> bool:
        return True

    @staticmethod
    def _keyring_module() -> KeyringModuleProtocol:
        try:
            import keyring
        except ImportError as error:
            raise SecretStoreError(
                "Системное хранилище секретов недоступно в этой сборке."
            ) from error
        return cast(KeyringModuleProtocol, keyring)

    def get_gemini_api_key(self) -> str | None:
        try:
            value = self._keyring_module().get_password(
                GEMINI_KEY_SERVICE,
                GEMINI_KEY_USERNAME,
            )
        except Exception as error:
            if sys.platform == "darwin":
                return self._macos_get_password(error)
            logger.warning(
                "Could not read Gemini key from the system keyring: type=%s",
                type(error).__name__,
            )
            raise SecretStoreError("Не удалось прочитать ключ из системного хранилища.") from error
        normalized = value.strip() if value else ""
        return normalized or None

    def set_gemini_api_key(self, api_key: str) -> None:
        normalized = api_key.strip()
        if not normalized:
            raise SecretStoreError("API-ключ не может быть пустым.")
        try:
            self._keyring_module().set_password(
                GEMINI_KEY_SERVICE,
                GEMINI_KEY_USERNAME,
                normalized,
            )
        except Exception as error:
            if sys.platform == "darwin":
                self._macos_set_password(normalized, error)
                return
            logger.warning(
                "Could not save Gemini key to the system keyring: type=%s",
                type(error).__name__,
            )
            raise SecretStoreError("Не удалось сохранить ключ в системном хранилище.") from error

    def delete_gemini_api_key(self) -> None:
        try:
            keyring = self._keyring_module()
            if keyring.get_password(GEMINI_KEY_SERVICE, GEMINI_KEY_USERNAME) is not None:
                keyring.delete_password(GEMINI_KEY_SERVICE, GEMINI_KEY_USERNAME)
        except Exception as error:
            if sys.platform == "darwin":
                self._macos_delete_password(error)
                return
            logger.warning(
                "Could not delete Gemini key from the system keyring: type=%s",
                type(error).__name__,
            )
            raise SecretStoreError("Не удалось удалить ключ из системного хранилища.") from error

    @staticmethod
    def _run_macos_security(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["security", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def _macos_get_password(self, keyring_error: Exception) -> str | None:
        try:
            result = self._run_macos_security(
                ["find-generic-password", "-s", GEMINI_KEY_SERVICE, "-a", GEMINI_KEY_USERNAME, "-w"]
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SecretStoreError("Не удалось прочитать ключ из системного хранилища.") from error
        if result.returncode == 44:
            return None
        if result.returncode != 0:
            logger.warning(
                "macOS Keychain fallback could not read Gemini key: keyring_error=%s exit=%s",
                type(keyring_error).__name__, result.returncode,
            )
            raise SecretStoreError(
                "Не удалось прочитать ключ из системного хранилища."
            ) from keyring_error
        normalized = result.stdout.strip()
        return normalized or None

    def _macos_set_password(self, api_key: str, keyring_error: Exception) -> None:
        try:
            result = self._run_macos_security(
                [
                    "add-generic-password", "-U", "-s", GEMINI_KEY_SERVICE,
                    "-a", GEMINI_KEY_USERNAME, "-w", api_key,
                ]
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SecretStoreError("Не удалось сохранить ключ в системном хранилище.") from error
        if result.returncode != 0:
            logger.warning(
                "macOS Keychain fallback could not save Gemini key: keyring_error=%s exit=%s",
                type(keyring_error).__name__, result.returncode,
            )
            raise SecretStoreError(
                "Не удалось сохранить ключ в системном хранилище."
            ) from keyring_error

    def _macos_delete_password(self, keyring_error: Exception) -> None:
        try:
            result = self._run_macos_security(
                ["delete-generic-password", "-s", GEMINI_KEY_SERVICE, "-a", GEMINI_KEY_USERNAME]
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SecretStoreError("Не удалось удалить ключ из системного хранилища.") from error
        if result.returncode not in {0, 44}:
            logger.warning(
                "macOS Keychain fallback could not delete Gemini key: keyring_error=%s exit=%s",
                type(keyring_error).__name__, result.returncode,
            )
            raise SecretStoreError(
                "Не удалось удалить ключ из системного хранилища."
            ) from keyring_error


def create_secret_store(
    settings: Settings,
    *,
    desktop_mode: bool,
) -> SecretStoreProtocol:
    if desktop_mode:
        return SystemKeyringSecretStore()
    return EnvironmentSecretStore(settings)
