from pathlib import Path
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
            test_client.testing_session_local = testing_session_local
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def configure_upload_directory(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        resolve_path=lambda path: tmp_path / path,
        output_dir=Path("data/processed"),
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

    # Background thread ko test ke andar synchronously run karo.
    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(video_router, "Thread", ImmediateThread)

    # Background worker ko test database use karwao.
    monkeypatch.setattr(
        video_router,
        "SessionLocal",
        client.testing_session_local,
    )

    class FakeVideoProcessingService:
        def process_video(
            self,
            video_path,
            output_video_path=None,
            on_frame_processed=None,
            on_progress=None,
        ):
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

            if on_frame_processed:
                on_frame_processed(output)

            if output_video_path is not None:
                output_video_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                output_video_path.write_bytes(b"fake-annotated-video")

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

    assert response.status_code == 202

    upload_result = response.json()
    processing_id = upload_result["processing_id"]

    status_response = client.get(
        f"/api/v1/videos/{processing_id}/status"
    )

    assert status_response.status_code == 200

    status_result = status_response.json()

    assert status_result["status"] == "completed"

    result = status_result["result"]

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
    assert result["plates_identified"] == 1
    assert result["recognized_plates"][0]["plate_number"] == "ABC123"

    saved_response = client.get("/api/v1/violations")

    assert saved_response.status_code == 200
    assert saved_response.json()["total"] == 1

    output_response = client.get(
        f"/api/v1/videos/{processing_id}/output"
    )

    assert output_response.status_code == 200

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
    monkeypatch.setattr(
        video_router,
        "MAX_UPLOAD_SIZE_BYTES",
        3,
    )

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