import sentry_sdk

from app.core.config import get_settings
from app.core.sentry import init_sentry
from app.main import app, create_app


def _collect_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
        inner = getattr(route, "routes", None) or getattr(
            getattr(route, "original_router", None), "routes", None
        )
        if inner:
            paths |= _collect_paths(inner)
    return paths


def test_create_app_exposes_platform_routes() -> None:
    test_app = create_app()
    paths = _collect_paths(test_app.routes)
    assert {"/health", "/ready", "/metrics"} <= paths
    assert "/api/v1/flags" in paths


async def test_lifespan_starts_and_stops_cleanly() -> None:
    async with app.router.lifespan_context(app):
        assert app.title == "OrderFlow Platform"


def test_settings_have_sane_defaults() -> None:
    settings = get_settings()
    assert settings.app_name
    assert isinstance(settings.cors_origins, list)
    assert 0.0 <= settings.sentry_traces_sample_rate <= 1.0


def test_init_sentry_without_dsn_does_nothing() -> None:
    init_sentry("", environment="test", release="test@1.0.0", traces_sample_rate=0.0)


def test_init_sentry_initializes_sdk_when_dsn_present(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))

    init_sentry(
        "https://public@example.com/1",
        environment="test",
        release="test@1.0.0",
        traces_sample_rate=0.25,
    )

    assert captured["dsn"] == "https://public@example.com/1"
    assert captured["environment"] == "test"
    assert captured["traces_sample_rate"] == 0.25
