"""HTTP smoke-проверка запущенного API (только stdlib, работает в CI и в deploy).

Запуск:  python scripts/smoke_check.py http://127.0.0.1:8000
Выход: 0 — все эндпоинты ответили корректно, 1 — иначе.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
RETRIES = 30
DELAY_SECONDS = 2


def _get(url: str, timeout: float = 5.0) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers={"X-Request-ID": "smoke-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body, response.headers.get("X-Request-ID", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, exc.headers.get("X-Request-ID", "") if exc.headers else ""


def wait_until_ready(base_url: str) -> bool:
    for attempt in range(1, RETRIES + 1):
        try:
            status, _, _ = _get(f"{base_url}/health")
        except (urllib.error.URLError, OSError):
            status = 0
        if status == 200:
            print(f"[smoke] api answered on attempt {attempt}")
            return True
        print(f"[smoke] waiting for {base_url}/health ({attempt}/{RETRIES})")
        time.sleep(DELAY_SECONDS)
    return False


def main() -> int:
    base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else DEFAULT_BASE_URL
    failures: list[str] = []

    if not wait_until_ready(base_url):
        print("[smoke] FAIL: /health never returned 200", file=sys.stderr)
        return 1

    status, body, request_id = _get(f"{base_url}/health")
    if status != 200 or json.loads(body).get("status") != "ok":
        failures.append(f"/health -> {status} {body}")
    if not request_id:
        failures.append("/health: X-Request-ID header is missing")

    status, body, _ = _get(f"{base_url}/ready")
    if status != 200:
        failures.append(f"/ready -> {status} {body}")

    status, body, _ = _get(f"{base_url}/metrics")
    if status != 200 or "http_requests_total" not in body:
        failures.append(f"/metrics -> {status} (counter is missing)")

    status, body, _ = _get(f"{base_url}/api/v1/flags")
    if status != 200 or not isinstance(json.loads(body), list):
        failures.append(f"/api/v1/flags -> {status} {body}")

    if failures:
        for failure in failures:
            print(f"[smoke] FAIL {failure}", file=sys.stderr)
        return 1

    print(f"[smoke] OK {base_url}: health, ready, metrics, flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
