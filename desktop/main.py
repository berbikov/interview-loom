import html
import logging
import os
import socket
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn
import webview
from filelock import FileLock, Timeout
from platformdirs import user_data_path, user_log_path

from app.metadata import APP_AUTHOR, APP_NAME
from desktop.macos_media import configure_macos_media_permissions

HOST = "127.0.0.1"
logger = logging.getLogger(__name__)


class DesktopApi:
    def __init__(self, app_url: str) -> None:
        self.app_url = app_url

    def report_media_capabilities(self, payload: object) -> None:
        if not isinstance(payload, dict):
            logger.warning("Desktop media capability payload has unexpected type")
            return
        safe_payload = {
            key: value
            for key, value in payload.items()
            if isinstance(key, str)
            and key
            in {
                "secureContext",
                "mediaDevices",
                "getUserMedia",
                "getDisplayMedia",
                "mediaRecorder",
                "userAgent",
            }
            and isinstance(value, (bool, str))
        }
        logger.info("Desktop media capabilities: %s", safe_payload)

    def open_recording_in_browser(self) -> bool:
        logger.info("Opening recording studio in the system browser")
        return webbrowser.open(f"{self.app_url}/record", new=2)


def desktop_data_dir() -> Path:
    return Path(user_data_path(APP_NAME, APP_AUTHOR, ensure_exists=True))


def desktop_log_dir() -> Path:
    return Path(user_log_path(APP_NAME, APP_AUTHOR, ensure_exists=True))


def bundled_assets_root() -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if isinstance(packaged_root, str):
        return Path(packaged_root)
    resource_path = os.environ.get("RESOURCEPATH")
    if resource_path:
        return Path(resource_path)
    return Path(__file__).resolve().parent.parent


def configure_desktop_environment(data_dir: Path | None = None) -> Path:
    resolved_data_dir = data_dir or desktop_data_dir()
    resolved_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["INTERVIEW_LOOM_DESKTOP"] = "1"
    os.environ["INTERVIEW_LOOM_DATA_DIR"] = str(resolved_data_dir)
    os.environ["INTERVIEW_LOOM_ASSETS_ROOT"] = str(bundled_assets_root())
    os.environ.setdefault("ENVIRONMENT", "desktop")
    return resolved_data_dir


def configure_desktop_logging(log_dir: Path | None = None) -> None:
    resolved_log_dir = log_dir or desktop_log_dir()
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                resolved_log_dir / "interview-loom.log",
                encoding="utf-8",
            )
        ],
        force=True,
    )


def find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_socket:
        port_socket.bind((HOST, 0))
        return int(port_socket.getsockname()[1])


def wait_until_ready(url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.15)
    raise RuntimeError("Локальный сервер Interview Loom не запустился вовремя.")


def show_desktop_error(title: str, message: str) -> None:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    webview.create_window(
        APP_NAME,
        html=(
            "<!doctype html><html lang='ru'><meta charset='utf-8'>"
            "<style>body{font-family:-apple-system,sans-serif;background:#f7f7f4;"
            "color:#171816;padding:48px}main{max-width:560px;margin:auto;background:white;"
            "border-radius:24px;padding:34px;box-shadow:0 20px 55px #0001}"
            "h1{font-size:30px}p{color:#666;line-height:1.55}</style>"
            f"<main><h1>{safe_title}</h1><p>{safe_message}</p></main></html>"
        ),
        width=680,
        height=420,
        resizable=False,
    )
    webview.start()


def run_desktop_application(data_dir: Path) -> None:
    from app.main import create_app

    port = find_available_port()
    app_url = f"http://{HOST}:{port}"
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=HOST,
            port=port,
            log_level="info",
            access_log=False,
        )
    )
    server_thread = threading.Thread(
        target=server.run,
        name="interview-loom-server",
        daemon=True,
    )
    server_thread.start()

    try:
        wait_until_ready(app_url)
        configure_macos_media_permissions()
        webview.create_window(
            APP_NAME,
            app_url,
            width=1280,
            height=820,
            min_size=(900, 650),
            background_color="#f7f7f4",
            js_api=DesktopApi(app_url),
        )
        webview.start(
            private_mode=False,
            storage_path=str(data_dir / "webview"),
        )
    finally:
        server.should_exit = True
        server_thread.join(timeout=8)


def run_smoke_test() -> None:
    smoke_data_dir = Path(tempfile.mkdtemp(prefix="interview-loom-smoke-"))
    configure_desktop_environment(smoke_data_dir)
    from app.main import create_app

    application = create_app()
    expected_routes = {
        "index_page": "/",
        "record_page": "/record",
        "health_check": "/health",
        "create_recording": "/api/recordings",
    }
    resolved_routes = {
        route_name: str(application.url_path_for(route_name))
        for route_name in expected_routes
    }
    if resolved_routes != expected_routes:
        raise RuntimeError(f"Unexpected route map: {resolved_routes}")


def run() -> None:
    data_dir = configure_desktop_environment()
    configure_desktop_logging()
    instance_lock = FileLock(data_dir / ".instance.lock")

    try:
        instance_lock.acquire(timeout=0)
    except Timeout:
        show_desktop_error(
            "Interview Loom уже открыт",
            "Вернитесь в запущенное окно приложения или закройте его перед повторным запуском.",
        )
        return

    try:
        run_desktop_application(data_dir)
    except Exception:
        logger.exception("Desktop application startup failed")
        show_desktop_error(
            "Не удалось запустить приложение",
            "Перезапустите Interview Loom. Если ошибка повторяется, "
            "приложите файл журнала из папки данных приложения.",
        )
    finally:
        instance_lock.release()


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        run_smoke_test()
    else:
        run()
