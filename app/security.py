from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_same_origin_request(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed_origin = urlsplit(origin)
    request_host = request.url.hostname
    request_port = request.url.port
    default_port = 443 if parsed_origin.scheme == "https" else 80
    origin_port = parsed_origin.port or default_port
    expected_port = request_port or (443 if request.url.scheme == "https" else 80)
    return (
        parsed_origin.scheme in {"http", "https"}
        and parsed_origin.hostname == request_host
        and origin_port == expected_port
    )


async def security_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.method in UNSAFE_METHODS and not is_same_origin_request(request):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Запрос с внешнего сайта отклонён."},
        )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = (
        "camera=(self), microphone=(self), display-capture=(self)"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
