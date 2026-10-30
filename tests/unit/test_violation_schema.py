from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.violation import (
    ViolationCreate,
    ViolationListResponse,
    ViolationResponse,
)


def test_valid_violation_create():
    violation = ViolationCreate(
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        video_source="test_video.mp4",
    )

    assert violation.track_id == 10
    assert violation.plate_number == "ABC123"
    assert violation.speed_kmh == 85.5


def test_violation_create_allows_optional_fields():
    violation = ViolationCreate(
        track_id=1,
        speed_kmh=80.0,
        speed_limit_kmh=60.0,
    )

    assert violation.plate_number is None
    assert violation.violation_time is None
    assert violation.video_source is None


@pytest.mark.parametrize(
    "payload",
    [
        {"track_id": 0, "speed_kmh": 80, "speed_limit_kmh": 60},
        {"track_id": 1, "speed_kmh": 0, "speed_limit_kmh": 60},
        {"track_id": 1, "speed_kmh": 80, "speed_limit_kmh": 0},
    ],
)
def test_violation_create_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        ViolationCreate(**payload)


def test_violation_response_from_attributes():
    class FakeViolation:
        id = 1
        track_id = 10
        plate_number = "ABC123"
        speed_kmh = 85.5
        speed_limit_kmh = 60.0
        violation_time = datetime(2026, 10, 30, 12, 0)
        video_source = "test_video.mp4"

    response = ViolationResponse.model_validate(FakeViolation())

    assert response.id == 1
    assert response.track_id == 10
    assert response.plate_number == "ABC123"


def test_violation_list_response():
    item = ViolationResponse(
        id=1,
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=datetime(2026, 10, 30, 12, 0),
        video_source="test_video.mp4",
    )

    response = ViolationListResponse(
        items=[item],
        total=1,
        limit=100,
        offset=0,
    )

    assert len(response.items) == 1
    assert response.total == 1
