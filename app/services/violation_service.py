from app.repositories.violation_repository import ViolationRepository
from app.schemas.violation import ViolationCreate


class ViolationService:
    """Handle vehicle violation business operations."""

    def __init__(self, repository: ViolationRepository) -> None:
        self.repository = repository

    def create_violation(self, data: ViolationCreate):
        """Validate and persist a vehicle violation."""
        return self.repository.create(
            track_id=data.track_id,
            plate_number=data.plate_number,
            speed_kmh=data.speed_kmh,
            speed_limit_kmh=data.speed_limit_kmh,
            violation_time=data.violation_time,
            video_source=data.video_source,
        )

    def get_violation(self, violation_id: int):
        """Retrieve a violation by ID."""
        return self.repository.get_by_id(violation_id)

    def get_violations(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ):
        """Retrieve violations with pagination."""
        return self.repository.get_all(
            limit=limit,
            offset=offset,
        )

    def count_violations(self) -> int:
        """Return the total number of stored violations."""
        return self.repository.count()
