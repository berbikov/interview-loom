import logging
import sys
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class SecurityOrigin(Protocol):
    def host(self) -> str: ...

    def protocol(self) -> str: ...


def is_trusted_media_origin(host: str, protocol: str) -> bool:
    """Allow capture only for the loopback server owned by the desktop app."""
    return host in {"127.0.0.1", "localhost"} and protocol in {"http", "https"}


def configure_macos_media_permissions() -> None:
    if sys.platform != "darwin":
        return

    import WebKit  # type: ignore[import-untyped]
    from webview.platforms.cocoa import BrowserView

    original_delegate = BrowserView.BrowserDelegate

    class LocalMediaPermissionDelegate(original_delegate):  # type: ignore[misc, valid-type]
        def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
            self,
            webview: object,
            origin: SecurityOrigin,
            frame: object,
            capture_type: int,
            decision_handler: Callable[[int], None],
        ) -> None:
            del webview, frame, capture_type
            host = str(origin.host())
            protocol = str(origin.protocol())
            if is_trusted_media_origin(host, protocol):
                logger.info("Granting media capture to the local desktop application")
                decision_handler(WebKit.WKPermissionDecisionGrant)
                return
            logger.warning("Denied media capture for an untrusted origin: %s", host)
            decision_handler(WebKit.WKPermissionDecisionDeny)

    BrowserView.BrowserDelegate = LocalMediaPermissionDelegate  # type: ignore[misc]
