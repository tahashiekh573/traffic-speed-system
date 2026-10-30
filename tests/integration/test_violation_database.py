from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.vehicle_violation import VehicleViolation  # noqa: F401
from app.repositories.violation_repository import ViolationRepository


def test_violation_repository_database_integration():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    try:
        with TestingSessionLocal() as session:
            repository = ViolationRepository(session)

            violation = repository.create(
                track_id=101,
                plate_number="ABC123",
                speed_kmh=85.5,
                speed_limit_kmh=60.0,
                video_source="integration_test.mp4",
            )

            session.commit()
            session.refresh(violation)

            saved_violation = repository.get_by_id(violation.id)
            all_violations = repository.get_all(limit=10, offset=0)

            assert saved_violation is not None
            assert saved_violation.track_id == 101
            assert saved_violation.plate_number == "ABC123"
            assert saved_violation.speed_kmh == 85.5
            assert len(all_violations) == 1
            assert repository.count() == 1

    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

