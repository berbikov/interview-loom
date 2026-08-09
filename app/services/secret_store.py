import logging
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
            logger.warning("Could not read Gemini key from the system keyring")
            raise SecretStoreError(
                "Не удалось прочитать ключ из системного хранилища."
            ) from error
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
            logger.warning("Could not save Gemini key to the system keyring")
            raise SecretStoreError(
                "Не удалось сохранить ключ в системном хранилище."
            ) from error

    def delete_gemini_api_key(self) -> None:
        try:
            keyring = self._keyring_module()
            if keyring.get_password(GEMINI_KEY_SERVICE, GEMINI_KEY_USERNAME) is not None:
                keyring.delete_password(GEMINI_KEY_SERVICE, GEMINI_KEY_USERNAME)
        except Exception as error:
            logger.warning("Could not delete Gemini key from the system keyring")
            raise SecretStoreError(
                "Не удалось удалить ключ из системного хранилища."
            ) from error


def create_secret_store(
    settings: Settings,
    *,
    desktop_mode: bool,
) -> SecretStoreProtocol:
    if desktop_mode:
        return SystemKeyringSecretStore()
    return EnvironmentSecretStore(settings)
