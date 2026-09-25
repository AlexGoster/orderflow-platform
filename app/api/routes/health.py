import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import request_id_var

logger = logging.getLogger("orderflow.health")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: процесс жив и отвечает. Не трогает зависимости."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Readiness: проверяет доступность БД; при падении зависимости — 503."""
    checks = {"database": "up"}
    status_code = status.HTTP_200_OK
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        checks["database"] = "down"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning(
            "readiness check failed",
            extra={"request_id": request_id_var.get(), "error": str(exc)},
        )
    body = {
        "status": "ready" if status_code == status.HTTP_200_OK else "not_ready",
        "checks": checks,
    }
    return JSONResponse(status_code=status_code, content=body)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus scrape endpoint: request counter + latency histogram."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
