import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var
from app.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

logger = logging.getLogger("orderflow.access")

_ID_SEGMENT = re.compile(r"/\d+")
_MAX_PATH_LENGTH = 120
_MAX_REQUEST_ID_LENGTH = 64


def normalize_path(path: str) -> str:
    """Гасит cardinality метрик: /api/v1/flags/42 -> /api/v1/flags/:id."""
    normalized = _ID_SEGMENT.sub("/:id", path)
    return normalized[:_MAX_PATH_LENGTH]


def _extract_request_id(scope: Scope) -> str:
    headers = Headers(scope=scope)
    incoming = headers.get("x-request-id", "")
    if incoming and len(incoming) <= _MAX_REQUEST_ID_LENGTH and incoming.isascii():
        return incoming
    return uuid.uuid4().hex


class RequestContextMiddleware:
    """ASGI-middleware: X-Request-ID, структурированный access-лог, метрики."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)
        token = request_id_var.set(request_id)
        method = str(scope.get("method", "GET"))
        raw_path = str(scope.get("path", "/"))
        path = normalize_path(raw_path)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            status_label = str(status_code)
            client = scope.get("client")
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status_label).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": raw_path,
                    "route": path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client": str(client[0]) if client else "",
                },
            )
            request_id_var.reset(token)
