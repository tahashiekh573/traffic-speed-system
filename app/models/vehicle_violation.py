from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VehicleViolation(Base):
    """Store detected vehicle speed violations."""

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

    speed_kmh: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    speed_limit_kmh: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    violation_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    video_source: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
