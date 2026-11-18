from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime for SQLite storage."""
    return datetime.now(UTC).replace(tzinfo=None)


VIOLATION_OVERSPEED = "overspeed"
VIOLATION_NO_HELMET = "no_helmet"


class VehicleViolation(Base):
    """Store detected traffic violations (overspeeding or riding without a helmet)."""

    __tablename__ = "vehicle_violations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    track_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    plate_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    violation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VIOLATION_OVERSPEED,
        server_default=VIOLATION_OVERSPEED,
        index=True,
    )

    # Unknown for a helmet violation when the speed was not measured.
    speed_kmh: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    speed_limit_kmh: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    violation_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
    )

    video_source: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
