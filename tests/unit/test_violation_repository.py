from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.violation_repository import ViolationRepository


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_create_violation(db_session):
    repository = ViolationRepository(db_session)
    timestamp = datetime(2026, 10, 30, 12, 0, 0)

    violation = repository.create(
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=timestamp,
        video_source="test_video.mp4",
    )

    assert violation.id is not None
    assert violation.track_id == 10
    assert violation.plate_number == "ABC123"
    assert violation.speed_kmh == 85.5
    assert violation.speed_limit_kmh == 60.0
    assert violation.violation_time == timestamp
    assert violation.video_source == "test_video.mp4"


def test_get_violation_by_id(db_session):
    repository = ViolationRepository(db_session)

    created = repository.create(
        track_id=20,
        speed_kmh=90.0,
        speed_limit_kmh=60.0,
        plate_number="XYZ789",
    )

    retrieved = repository.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.track_id == 20
    assert retrieved.plate_number == "XYZ789"


def test_get_violation_by_id_returns_none_when_missing(db_session):
    repository = ViolationRepository(db_session)

    assert repository.get_by_id(999) is None


def test_get_all_violations_with_pagination(db_session):
    repository = ViolationRepository(db_session)

    for track_id in (1, 2, 3):
        repository.create(
            track_id=track_id,
            speed_kmh=80.0 + track_id,
            speed_limit_kmh=60.0,
        )

    results = repository.get_all(limit=2, offset=0)

    assert len(results) == 2
    assert [item.track_id for item in results] == [3, 2]


def test_get_all_violations_with_offset(db_session):
    repository = ViolationRepository(db_session)

    for track_id in (1, 2, 3):
        repository.create(
            track_id=track_id,
            speed_kmh=80.0,
            speed_limit_kmh=60.0,
        )

    results = repository.get_all(limit=2, offset=1)

    assert len(results) == 2
    assert [item.track_id for item in results] == [2, 1]
