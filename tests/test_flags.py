from httpx import AsyncClient

FLAG = {
    "key": "new-checkout",
    "description": "Новый чекаут на фронтенде",
    "enabled": True,
    "rollout_percent": 10,
}


async def test_create_flag_returns_201(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/flags", json=FLAG)
    assert resp.status_code == 201
    payload = resp.json()
    assert payload["key"] == "new-checkout"
    assert payload["enabled"] is True
    assert payload["rollout_percent"] == 10
    assert payload["id"] >= 1
    assert payload["created_at"]


async def test_create_duplicate_flag_returns_409(client: AsyncClient) -> None:
    await client.post("/api/v1/flags", json=FLAG)
    resp = await client.post("/api/v1/flags", json=FLAG)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_create_flag_validation_error(client: AsyncClient) -> None:
    bad_key = {**FLAG, "key": "Bad Key!"}
    resp = await client.post("/api/v1/flags", json=bad_key)
    assert resp.status_code == 422

    bad_rollout = {**FLAG, "rollout_percent": 150}
    resp = await client.post("/api/v1/flags", json=bad_rollout)
    assert resp.status_code == 422


async def test_list_flags_sorted_by_key(client: AsyncClient) -> None:
    await client.post("/api/v1/flags", json={**FLAG, "key": "zeta"})
    await client.post("/api/v1/flags", json={**FLAG, "key": "alpha"})

    resp = await client.get("/api/v1/flags")
    assert resp.status_code == 200
    keys = [item["key"] for item in resp.json()]
    assert keys == ["alpha", "zeta"]


async def test_get_flag_by_key(client: AsyncClient) -> None:
    await client.post("/api/v1/flags", json=FLAG)
    resp = await client.get("/api/v1/flags/new-checkout")
    assert resp.status_code == 200
    assert resp.json()["description"] == FLAG["description"]


async def test_get_missing_flag_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/flags/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_update_flag(client: AsyncClient) -> None:
    await client.post("/api/v1/flags", json=FLAG)

    resp = await client.patch(
        "/api/v1/flags/new-checkout",
        json={"enabled": False, "rollout_percent": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["rollout_percent"] == 100

    unchanged = await client.get("/api/v1/flags/new-checkout")
    assert unchanged.json()["description"] == FLAG["description"]


async def test_update_missing_flag_returns_404(client: AsyncClient) -> None:
    resp = await client.patch("/api/v1/flags/nope", json={"enabled": True})
    assert resp.status_code == 404


async def test_delete_flag_then_missing(client: AsyncClient) -> None:
    await client.post("/api/v1/flags", json=FLAG)

    deleted = await client.delete("/api/v1/flags/new-checkout")
    assert deleted.status_code == 204

    after = await client.get("/api/v1/flags/new-checkout")
    assert after.status_code == 404


async def test_delete_missing_flag_returns_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/flags/nope")
    assert resp.status_code == 404
