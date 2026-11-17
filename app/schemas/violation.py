from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_utc(value: datetime | None) -> datetime | None:
    """Mark naive database timestamps as UTC so clients convert correctly."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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

    @field_validator("violation_time")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        """Serialize violation times with an explicit UTC offset."""
        return _as_utc(value)


class ViolationListResponse(BaseModel):
    """Represent a paginated list of violations."""

    items: list[ViolationResponse]
    total: int
    limit: int
    offset: int


class ViolationStatisticsResponse(BaseModel):
    """Aggregate figures across all stored violations."""

    total_violations: int
    average_speed_kmh: float | None
    max_speed_kmh: float | None
    violations_with_plate: int
    videos_analyzed: int
    latest_violation_time: datetime | None

    @field_validator("latest_violation_time")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        """Serialize the latest time with an explicit UTC offset."""
        return _as_utc(value)
