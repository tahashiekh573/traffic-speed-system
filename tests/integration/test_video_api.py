from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.vehicle_violation import VehicleViolation  # noqa: F401
from app.routers import video_router
from app.services.video_processing_service import VideoProcessingResult


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def configure_upload_directory(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        resolve_path=lambda path: tmp_path / path,
        speed_limit_kmh=60.0,
    )
    monkeypatch.setattr(video_router, "get_settings", lambda: settings)
    return tmp_path / "data" / "videos"


def test_video_upload_processes_video_and_saves_violation(
    client,
    monkeypatch,
    tmp_path,
):
    upload_dir = configure_upload_directory(monkeypatch, tmp_path)

    class FakeVideoProcessingService:
        def process_video(self, video_path, on_frame_processed=None):
            output = SimpleNamespace(
                plate_output=SimpleNamespace(
                    readings=[
                        SimpleNamespace(
                            track_id=7,
                            plate_text="ABC123",
                        )
                    ]
                ),
                speed_output=SimpleNamespace(
                    measurements=[
                        SimpleNamespace(
                            track_id=7,
                            speed_kmh=85.0,
                            is_overspeeding=True,
                        )
                    ]
                ),
            )

            on_frame_processed(output)

            return VideoProcessingResult(
                video_path=str(video_path),
                fps=30.0,
                width=640,
                height=480,
                total_frames=10,
                processed_frames=10,
            )

    monkeypatch.setattr(
        video_router,
        "VideoProcessingService",
        FakeVideoProcessingService,
    )

    response = client.post(
        "/api/v1/videos/process",
        files={
            "file": (
                "traffic.mp4",
                b"fake-video-content",
                "video/mp4",
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["filename"] == "traffic.mp4"
    assert result["fps"] == 30.0
    assert result["width"] == 640
    assert result["height"] == 480
    assert result["total_frames"] == 10
    assert result["processed_frames"] == 10
    assert result["violations_saved"] == 1
    assert result["violations"][0]["track_id"] == 7
    assert result["violations"][0]["plate_number"] == "ABC123"
    assert result["violations"][0]["speed_kmh"] == 85.0

    saved_response = client.get("/api/v1/violations")

    assert saved_response.status_code == 200
    assert saved_response.json()["total"] == 1

    assert list(upload_dir.iterdir()) == []


def test_video_upload_rejects_unsupported_extension(client):
    response = client.post(
        "/api/v1/videos/process",
        files={
            "file": (
                "document.txt",
                b"not-a-video",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415


def test_video_upload_rejects_empty_file(
    client,
    monkeypatch,
    tmp_path,
):
    upload_dir = configure_upload_directory(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/videos/process",
        files={
            "file": (
                "empty.mp4",
                b"",
                "video/mp4",
            )
        },
    )

    assert response.status_code == 400
    assert list(upload_dir.iterdir()) == []


def test_video_upload_rejects_file_exceeding_size_limit(
    client,
    monkeypatch,
    tmp_path,
):
    upload_dir = configure_upload_directory(monkeypatch, tmp_path)
    monkeypatch.setattr(video_router, "MAX_UPLOAD_SIZE_BYTES", 3)

    response = client.post(
        "/api/v1/videos/process",
        files={
            "file": (
                "large.mp4",
                b"1234",
                "video/mp4",
            )
        },
    )

    assert response.status_code == 413
    assert list(upload_dir.iterdir()) == []
