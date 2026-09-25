from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_sets_request_id_header(client: AsyncClient) -> None:
    resp = await client.get("/health")
    request_id = resp.headers.get("X-Request-ID")
    assert request_id
    assert len(request_id) == 32


async def test_custom_request_id_is_echoed_back(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-ID": "cid-abc-123"})
    assert resp.headers["X-Request-ID"] == "cid-abc-123"


async def test_oversized_request_id_is_replaced(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-ID": "x" * 500})
    assert resp.headers["X-Request-ID"] != "x" * 500
    assert len(resp.headers["X-Request-ID"]) == 32


async def test_unknown_path_returns_404_with_request_id(client: AsyncClient) -> None:
    resp = await client.get("/definitely-missing")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}
    assert resp.headers.get("X-Request-ID")
