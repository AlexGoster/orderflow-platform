from httpx import AsyncClient


def _counter_value(body: str, method: str, path: str, status: str) -> float:
    target = f'http_requests_total{{method="{method}",path="{path}",status="{status}"}}'
    for line in body.splitlines():
        if line.startswith(target + " "):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


async def test_metrics_endpoint_is_available(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


async def test_metrics_expose_counter_and_latency_histogram(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds_bucket" in body
    assert "http_request_duration_seconds_count" in body
    assert "http_request_duration_seconds_sum" in body


async def test_metrics_count_requests_per_label(client: AsyncClient) -> None:
    before = _counter_value((await client.get("/metrics")).text, "GET", "/health", "200")

    await client.get("/health")
    await client.get("/health")

    after = _counter_value((await client.get("/metrics")).text, "GET", "/health", "200")
    assert after == before + 2


async def test_metrics_track_error_status_codes(client: AsyncClient) -> None:
    await client.get("/definitely-missing")

    body = (await client.get("/metrics")).text
    assert _counter_value(body, "GET", "/definitely-missing", "404") >= 1
