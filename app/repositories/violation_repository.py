from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.vehicle_violation import VehicleViolation


class ViolationRepository:
    """Manage vehicle violation records in the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        track_id: int,
        speed_kmh: float,
        speed_limit_kmh: float,
        plate_number: str | None = None,
        violation_time: datetime | None = None,
        video_source: str | None = None,
    ) -> VehicleViolation:
        """Create and save a vehicle violation."""
        violation = VehicleViolation(
            track_id=track_id,
            plate_number=plate_number,
            speed_kmh=speed_kmh,
            speed_limit_kmh=speed_limit_kmh,
            video_source=video_source,
        )

        if violation_time is not None:
            violation.violation_time = violation_time

        self.db.add(violation)

        try:
            self.db.commit()
            self.db.refresh(violation)
        except Exception:
            self.db.rollback()
            raise

        return violation

    def get_by_id(self, violation_id: int) -> VehicleViolation | None:
        """Retrieve a violation by its database ID."""
        statement = select(VehicleViolation).where(
            VehicleViolation.id == violation_id
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[VehicleViolation]:
        """Retrieve violations with pagination."""
        statement = (
            select(VehicleViolation)
            .order_by(VehicleViolation.id.desc())
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())


    def count(self) -> int:
        """Return the total number of stored violations."""
        statement = select(func.count()).select_from(VehicleViolation)
        return self.db.scalar(statement) or 0
