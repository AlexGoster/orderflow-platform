from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    description: str = Field(default="", max_length=255)
    enabled: bool = False
    rollout_percent: int = Field(default=0, ge=0, le=100)


class FeatureFlagUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)


class FeatureFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    description: str
    enabled: bool
    rollout_percent: int
    created_at: datetime
    updated_at: datetime
