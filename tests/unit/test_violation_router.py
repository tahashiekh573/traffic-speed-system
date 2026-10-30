from datetime import datetime
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.violation_router import (
    get_violation_service,
    router,
)

app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_create_violation_endpoint():
    service = Mock()
    service.create_violation.return_value = Mock(
        id=1,
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=datetime(2026, 10, 30, 12, 0),
        video_source="test_video.mp4",
    )

    app.dependency_overrides[get_violation_service] = lambda: service

    response = client.post(
        "/api/v1/violations",
        json={
            "track_id": 10,
            "plate_number": "ABC123",
            "speed_kmh": 85.5,
            "speed_limit_kmh": 60.0,
            "video_source": "test_video.mp4",
        },
    )

    assert response.status_code == 201
    assert response.json()["track_id"] == 10
    assert response.json()["plate_number"] == "ABC123"

    app.dependency_overrides.clear()


def test_get_violations_endpoint():
    service = Mock()
    service.get_violations.return_value = []
    service.count_violations.return_value = 25

    app.dependency_overrides[get_violation_service] = lambda: service

    response = client.get(
        "/api/v1/violations?limit=10&offset=5"
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 25
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 5

    app.dependency_overrides.clear()


def test_get_violation_by_id_endpoint():
    service = Mock()
    service.get_violation.return_value = Mock(
        id=1,
        track_id=10,
        plate_number="ABC123",
        speed_kmh=85.5,
        speed_limit_kmh=60.0,
        violation_time=datetime(2026, 10, 30, 12, 0),
        video_source="test_video.mp4",
    )

    app.dependency_overrides[get_violation_service] = lambda: service

    response = client.get("/api/v1/violations/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1

    app.dependency_overrides.clear()


def test_get_missing_violation_returns_404():
    service = Mock()
    service.get_violation.return_value = None

    app.dependency_overrides[get_violation_service] = lambda: service

    response = client.get("/api/v1/violations/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Violation not found."

    app.dependency_overrides.clear()


def test_create_violation_rejects_invalid_data():
    service = Mock()

    app.dependency_overrides[get_violation_service] = lambda: service

    response = client.post(
        "/api/v1/violations",
        json={
            "track_id": 0,
            "speed_kmh": 85.5,
            "speed_limit_kmh": 60.0,
        },
    )

    assert response.status_code == 422
    service.create_violation.assert_not_called()

    app.dependency_overrides.clear()
