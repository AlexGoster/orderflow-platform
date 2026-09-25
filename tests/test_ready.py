from httpx import AsyncClient

from app.core.database import get_session
from app.main import app


class _BrokenSession:
    """Заглушка сессии, у которой «упала» зависимость — БД недоступна."""

    async def execute(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("connection refused")


async def test_ready_returns_200_when_database_is_up(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "checks": {"database": "up"}}


async def test_ready_returns_503_when_database_is_down(client: AsyncClient) -> None:
    async def broken_session():
        yield _BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    resp = await client.get("/ready")

    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"] == "down"


async def test_ready_recover_after_dependency_back(client: AsyncClient, session_factory) -> None:
    async def broken_session():
        yield _BrokenSession()

    async def healthy_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    assert (await client.get("/ready")).status_code == 503

    app.dependency_overrides[get_session] = healthy_session
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["database"] == "up"
