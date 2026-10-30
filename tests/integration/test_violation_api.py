from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.vehicle_violation import VehicleViolation  # noqa: F401

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


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_violation_api_database_integration():
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/violations",
                json={
                    "track_id": 101,
                    "plate_number": "ABC123",
                    "speed_kmh": 85.5,
                    "speed_limit_kmh": 60.0,
                    "video_source": "integration_test.mp4",
                },
            )

            assert create_response.status_code == 201

            created = create_response.json()
            violation_id = created["id"]

            assert created["track_id"] == 101
            assert created["plate_number"] == "ABC123"

            list_response = client.get("/api/v1/violations")

            assert list_response.status_code == 200
            assert list_response.json()["total"] == 1
            assert len(list_response.json()["items"]) == 1

            detail_response = client.get(
                f"/api/v1/violations/{violation_id}"
            )

            assert detail_response.status_code == 200
            assert detail_response.json()["id"] == violation_id
            assert detail_response.json()["speed_kmh"] == 85.5

    finally:
        app.dependency_overrides.pop(get_db, None)


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
