from sqlalchemy import text

from app.core.config import Settings
from app.core.database import dispose_engine, get_engine, get_session, get_session_factory


def _sqlite_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite://")


async def test_get_engine_is_singleton(monkeypatch) -> None:
    monkeypatch.setattr("app.core.database.get_settings", _sqlite_settings)
    await dispose_engine()

    first = get_engine()
    second = get_engine()
    assert first is second

    await dispose_engine()


async def test_get_session_factory_is_cached(monkeypatch) -> None:
    monkeypatch.setattr("app.core.database.get_settings", _sqlite_settings)
    await dispose_engine()

    first = get_session_factory()
    second = get_session_factory()
    assert first is second

    await dispose_engine()


async def test_get_session_yields_working_session(monkeypatch) -> None:
    monkeypatch.setattr("app.core.database.get_settings", _sqlite_settings)
    await dispose_engine()

    agen = get_session()
    session = await agen.__anext__()
    try:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    finally:
        await agen.aclose()
        await dispose_engine()


async def test_dispose_engine_is_idempotent() -> None:
    await dispose_engine()
    await dispose_engine()
