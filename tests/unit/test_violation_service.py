from datetime import datetime
from unittest.mock import Mock

from app.schemas.violation import ViolationCreate
from app.services.violation_service import ViolationService


def test_create_violation():
    repository = Mock()
    expected = Mock()
    repository.create.return_value = expected

    service = ViolationService(repository)

    data = ViolationCreate(
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=datetime(2026, 10, 30, 12, 0),
        video_source="test_video.mp4",
    )

    result = service.create_violation(data)

    assert result is expected
    repository.create.assert_called_once_with(
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=datetime(2026, 10, 30, 12, 0),
        video_source="test_video.mp4",
    )


def test_get_violation():
    repository = Mock()
    expected = Mock()
    repository.get_by_id.return_value = expected

    service = ViolationService(repository)

    result = service.get_violation(5)

    assert result is expected
    repository.get_by_id.assert_called_once_with(5)


def test_get_violation_returns_none_when_missing():
    repository = Mock()
    repository.get_by_id.return_value = None

    service = ViolationService(repository)

    assert service.get_violation(999) is None


def test_get_violations_with_pagination():
    repository = Mock()
    expected = [Mock(), Mock()]
    repository.get_all.return_value = expected

    service = ViolationService(repository)

    result = service.get_violations(limit=2, offset=5)

    assert result == expected
    repository.get_all.assert_called_once_with(
        limit=2,
        offset=5,
    )
