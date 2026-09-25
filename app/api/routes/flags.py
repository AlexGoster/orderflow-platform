from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import FeatureFlag
from app.schemas import FeatureFlagCreate, FeatureFlagRead, FeatureFlagUpdate
from app.services import flags as flags_service

router = APIRouter(prefix="/api/v1/flags", tags=["flags"])


@router.post("", response_model=FeatureFlagRead, status_code=status.HTTP_201_CREATED)
async def create_flag(
    payload: FeatureFlagCreate,
    session: AsyncSession = Depends(get_session),
) -> FeatureFlag:
    return await flags_service.create_flag(session, payload)


@router.get("", response_model=list[FeatureFlagRead])
async def list_flags(session: AsyncSession = Depends(get_session)) -> list[FeatureFlag]:
    return await flags_service.list_flags(session)


@router.get("/{flag_key}", response_model=FeatureFlagRead)
async def get_flag(flag_key: str, session: AsyncSession = Depends(get_session)) -> FeatureFlag:
    return await flags_service.get_flag(session, flag_key)


@router.patch("/{flag_key}", response_model=FeatureFlagRead)
async def update_flag(
    flag_key: str,
    payload: FeatureFlagUpdate,
    session: AsyncSession = Depends(get_session),
) -> FeatureFlag:
    return await flags_service.update_flag(session, flag_key, payload)


@router.delete("/{flag_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flag(flag_key: str, session: AsyncSession = Depends(get_session)) -> Response:
    await flags_service.delete_flag(session, flag_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
