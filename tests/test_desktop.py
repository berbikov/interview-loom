import os
import socket
from pathlib import Path

import pytest

from desktop.macos_media import is_trusted_media_origin
from desktop.main import (
    HOST,
    DesktopApi,
    configure_desktop_environment,
    find_available_port,
    run_smoke_test,
)


class StubPortSocket:
    def __enter__(self) -> "StubPortSocket":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    def bind(self, address: tuple[str, int]) -> None:
        assert address == (HOST, 0)

    def getsockname(self) -> tuple[str, int]:
        return HOST, 49152


def test_desktop_launcher_selects_available_local_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_socket(address_family: int, socket_type: int) -> StubPortSocket:
        assert address_family == socket.AF_INET
        assert socket_type == socket.SOCK_STREAM
        return StubPortSocket()

    monkeypatch.setattr("desktop.main.socket.socket", create_socket)

    assert find_available_port() == 49152


def test_desktop_environment_uses_private_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERVIEW_LOOM_DATA_DIR", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    resolved_path = configure_desktop_environment(tmp_path)

    assert resolved_path == tmp_path
    assert tmp_path.is_dir()
    assert os.environ["INTERVIEW_LOOM_DATA_DIR"] == str(tmp_path)
    assert os.environ["ENVIRONMENT"] == "desktop"


def test_packaged_smoke_test_checks_required_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("desktop.main.tempfile.mkdtemp", lambda **_: str(tmp_path))

    run_smoke_test()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
@pytest.mark.parametrize("protocol", ["http", "https"])
def test_media_capture_allows_local_application(host: str, protocol: str) -> None:
    assert is_trusted_media_origin(host, protocol)


@pytest.mark.parametrize(
    ("host", "protocol"),
    [
        ("interview-loom.example", "https"),
        ("127.0.0.1.evil.example", "https"),
        ("127.0.0.1", "file"),
    ],
)
def test_media_capture_rejects_untrusted_origins(host: str, protocol: str) -> None:
    assert not is_trusted_media_origin(host, protocol)


def test_desktop_api_opens_recording_in_system_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_urls: list[tuple[str, int]] = []

    def open_browser(url: str, new: int) -> bool:
        opened_urls.append((url, new))
        return True

    monkeypatch.setattr("desktop.main.webbrowser.open", open_browser)

    assert DesktopApi("http://127.0.0.1:49152").open_recording_in_browser()
    assert opened_urls == [("http://127.0.0.1:49152/record", 2)]
