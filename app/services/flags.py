from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models import FeatureFlag
from app.schemas import FeatureFlagCreate, FeatureFlagUpdate


async def create_flag(session: AsyncSession, payload: FeatureFlagCreate) -> FeatureFlag:
    flag = FeatureFlag(**payload.model_dump())
    session.add(flag)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(f"Feature flag '{payload.key}' already exists") from exc
    return flag


async def list_flags(session: AsyncSession) -> list[FeatureFlag]:
    result = await session.scalars(select(FeatureFlag).order_by(FeatureFlag.key))
    return list(result)


async def get_flag(session: AsyncSession, flag_key: str) -> FeatureFlag:
    flag = await session.scalar(select(FeatureFlag).where(FeatureFlag.key == flag_key))
    if flag is None:
        raise NotFoundError(f"Feature flag '{flag_key}' not found")
    return flag


async def update_flag(
    session: AsyncSession, flag_key: str, payload: FeatureFlagUpdate
) -> FeatureFlag:
    flag = await get_flag(session, flag_key)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(flag, field, value)
    session.add(flag)
    await session.commit()
    return flag


async def delete_flag(session: AsyncSession, flag_key: str) -> None:
    flag = await get_flag(session, flag_key)
    await session.delete(flag)
    await session.commit()
