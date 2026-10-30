from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ViolationCreate(BaseModel):
    """Validate incoming vehicle violation data."""

    track_id: int = Field(gt=0)
    plate_number: str | None = Field(default=None, max_length=20)
    speed_kmh: float = Field(gt=0)
    speed_limit_kmh: float = Field(gt=0)
    violation_time: datetime | None = None
    video_source: str | None = Field(default=None, max_length=255)


class ViolationResponse(BaseModel):
    """Serialize a vehicle violation for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    plate_number: str | None
    speed_kmh: float
    speed_limit_kmh: float
    violation_time: datetime
    video_source: str | None


class ViolationListResponse(BaseModel):
    """Represent a paginated list of violations."""

    items: list[ViolationResponse]
    total: int
    limit: int
    offset: int
