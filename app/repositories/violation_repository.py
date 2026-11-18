from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.vehicle_violation import (
    VIOLATION_NO_HELMET,
    VIOLATION_OVERSPEED,
    VehicleViolation,
)


class ViolationRepository:
    """Manage vehicle violation records in the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        track_id: int,
        speed_kmh: float | None,
        speed_limit_kmh: float,
        plate_number: str | None = None,
        violation_time: datetime | None = None,
        video_source: str | None = None,
        violation_type: str = VIOLATION_OVERSPEED,
    ) -> VehicleViolation:
        """Create and save a vehicle violation."""
        violation = VehicleViolation(
            track_id=track_id,
            plate_number=plate_number,
            violation_type=violation_type,
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

    def update_plate(
        self,
        violation_id: int,
        plate_number: str,
    ) -> VehicleViolation | None:
        """Attach a plate number that was recognised after the violation."""
        violation = self.get_by_id(violation_id)

        if violation is None:
            return None

        violation.plate_number = plate_number

        try:
            self.db.commit()
            self.db.refresh(violation)
        except Exception:
            self.db.rollback()
            raise

        return violation

    def get_statistics(self) -> dict[str, float | int | datetime | None]:
        """Return aggregate figures across all stored violations."""
        statement = select(
            func.count(VehicleViolation.id),
            func.avg(VehicleViolation.speed_kmh),
            func.max(VehicleViolation.speed_kmh),
            func.count(VehicleViolation.plate_number),
            func.count(func.distinct(VehicleViolation.video_source)),
            func.max(VehicleViolation.violation_time),
            func.count(VehicleViolation.id).filter(
                VehicleViolation.violation_type == VIOLATION_OVERSPEED
            ),
            func.count(VehicleViolation.id).filter(
                VehicleViolation.violation_type == VIOLATION_NO_HELMET
            ),
        )

        (
            total,
            average,
            maximum,
            with_plate,
            videos,
            latest,
            overspeed,
            no_helmet,
        ) = self.db.execute(statement).one()

        return {
            "total_violations": int(total or 0),
            "average_speed_kmh": (
                round(float(average), 2) if average is not None else None
            ),
            "max_speed_kmh": (
                round(float(maximum), 2) if maximum is not None else None
            ),
            "violations_with_plate": int(with_plate or 0),
            "videos_analyzed": int(videos or 0),
            "latest_violation_time": latest,
            "overspeed_violations": int(overspeed or 0),
            "no_helmet_violations": int(no_helmet or 0),
        }
