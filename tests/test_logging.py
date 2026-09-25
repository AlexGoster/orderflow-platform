import json
import logging
import sys

from httpx import AsyncClient

from app.core.logging import JsonFormatter, request_id_var, setup_logging
from app.core.middleware import RequestContextMiddleware


def _record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="orderflow.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_json_formatter_produces_one_json_object() -> None:
    payload = json.loads(JsonFormatter().format(_record("hello")))
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "orderflow.test"
    assert payload["timestamp"].startswith("20")  # ISO-8601


def test_json_formatter_keeps_extra_fields() -> None:
    record = _record()
    record.status_code = 201
    record.duration_ms = 12.5

    payload = json.loads(JsonFormatter().format(record))
    assert payload["status_code"] == 201
    assert payload["duration_ms"] == 12.5


def test_json_formatter_reads_request_id_from_contextvar() -> None:
    token = request_id_var.set("ctx-rid-42")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "ctx-rid-42"


def test_json_formatter_does_not_duplicate_request_id() -> None:
    record = _record()
    record.request_id = "explicit-rid"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "explicit-rid"


async def test_access_log_carries_request_context(client: AsyncClient, caplog) -> None:
    caplog.set_level(logging.INFO)
    resp = await client.get("/health", headers={"X-Request-ID": "log-rid-1"})

    entries = [r for r in caplog.records if r.getMessage() == "request completed"]
    assert entries, "access log record was not emitted"
    record = entries[-1]
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == resp.headers["X-Request-ID"] == "log-rid-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] >= 0
    assert payload["route"] == "/health"


async def test_readiness_failure_is_logged_as_warning(client: AsyncClient, caplog) -> None:
    from app.core.database import get_session
    from app.main import app

    class _BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("db exploded")

    async def broken_session():
        yield _BrokenSession()

    caplog.set_level(logging.WARNING)
    app.dependency_overrides[get_session] = broken_session
    await client.get("/ready")

    messages = [r.getMessage() for r in caplog.records]
    assert "readiness check failed" in messages


def test_setup_logging_does_not_duplicate_handlers() -> None:
    root = logging.getLogger()
    handlers_before = len(root.handlers)

    setup_logging("INFO")
    setup_logging("INFO")

    assert len(root.handlers) == handlers_before
    assert root.level == logging.INFO
    assert any(
        isinstance(handler.formatter, JsonFormatter)
        for handler in root.handlers
        if handler.formatter is not None
    )


async def test_middleware_passes_through_non_http_scope() -> None:
    seen: dict[str, str] = {}

    async def inner_app(scope, receive, send) -> None:
        seen["type"] = str(scope["type"])

    middleware = RequestContextMiddleware(inner_app)
    await middleware({"type": "lifespan"}, None, None)

    assert seen["type"] == "lifespan"


def test_json_formatter_serializes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="orderflow.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
