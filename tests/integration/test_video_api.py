from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.vehicle_violation import VehicleViolation  # noqa: F401
from app.routers.video_router import get_video_job_service
from app.services.video_job_service import VideoJobService
from app.services.video_processing_service import (
    VideoProcessingResult,
    VideoProcessingService,
)
from app.services.video_progress_manager import VideoProgressManager


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
        app.dependency_overrides.pop(get_video_job_service, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def build_settings(tmp_path, **overrides):
    values = {
        "upload_dir": tmp_path / "data" / "videos",
        "output_dir": tmp_path / "data" / "processed",
        "speed_limit_kmh": 60.0,
    }
    values.update(overrides)
    return Settings(**values)


def install_job_service(
    client,
    tmp_path,
    processing_service_factory=VideoProcessingService,
    **overrides,
):
    """Use a job service that runs synchronously against the test DB."""
    settings = build_settings(tmp_path, **overrides)
    service = VideoJobService(
        settings=settings,
        progress_manager=VideoProgressManager(),
        session_factory=client.testing_session_local,
        processing_service_factory=processing_service_factory,
        background_runner=lambda target, args: target(*args),
    )
    app.dependency_overrides[get_video_job_service] = lambda: service
    return settings.resolved_upload_dir


def configure_upload_directory(client, tmp_path, **overrides):
    return install_job_service(client, tmp_path, **overrides)


class FakeVideoProcessingService:
    """Emit a plate reading after the overspeed measurement."""

    def process_video(
        self,
        video_path,
        output_video_path=None,
        on_frame_processed=None,
        on_progress=None,
    ):
        frames = [
            SimpleNamespace(
                tracks=[SimpleNamespace(track_id=7, class_name="car")],
                plate_output=SimpleNamespace(readings=[]),
                speed_output=SimpleNamespace(
                    measurements=[
                        SimpleNamespace(
                            track_id=7,
                            speed_kmh=85.0,
                            is_overspeeding=True,
                        ),
                        SimpleNamespace(
                            track_id=9,
                            speed_kmh=40.0,
                            is_overspeeding=False,
                        ),
                    ]
                ),
            ),
            SimpleNamespace(
                tracks=[SimpleNamespace(track_id=7, class_name="car")],
                plate_output=SimpleNamespace(
                    readings=[
                        SimpleNamespace(track_id=7, plate_text="ABC123")
                    ]
                ),
                speed_output=SimpleNamespace(measurements=[]),
            ),
        ]

        for output in frames:
            if on_frame_processed:
                on_frame_processed(output)

        if output_video_path is not None:
            output_video_path.parent.mkdir(parents=True, exist_ok=True)
            output_video_path.write_bytes(b"fake-annotated-video")

        return VideoProcessingResult(
            video_path=str(video_path),
            fps=30.0,
            width=640,
            height=480,
            total_frames=10,
            processed_frames=10,
        )


def test_video_upload_processes_video_and_saves_violation(
    client,
    tmp_path,
):
    upload_dir = install_job_service(
        client,
        tmp_path,
        processing_service_factory=FakeVideoProcessingService,
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
    assert result["vehicles_tracked"] == 1
    assert result["vehicle_types"] == {"car": 1}
    assert result["max_speed_kmh"] == 85.0
    assert result["average_speed_kmh"] == 62.5
    assert len(result["speed_records"]) == 2
    assert result["speed_records"][0]["plate_number"] == "ABC123"

    saved_response = client.get("/api/v1/violations")

    assert saved_response.status_code == 200
    assert saved_response.json()["total"] == 1
    # Plate recognised after the violation must be back-filled in the DB.
    assert saved_response.json()["items"][0]["plate_number"] == "ABC123"

    output_response = client.get(
        f"/api/v1/videos/{processing_id}/output"
    )

    assert output_response.status_code == 200

    assert list(upload_dir.iterdir()) == []


def test_video_upload_rejects_unsupported_extension(client, tmp_path):
    install_job_service(client, tmp_path)

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
    upload_dir = configure_upload_directory(client, tmp_path)

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
    upload_dir = configure_upload_directory(client, tmp_path)
    service = app.dependency_overrides[get_video_job_service]()
    monkeypatch.setattr(
        type(service.settings),
        "max_upload_size_bytes",
        property(lambda self: 3),
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

def test_status_returns_404_for_unknown_job(client, tmp_path):
    install_job_service(client, tmp_path)

    response = client.get("/api/v1/videos/missing/status")

    assert response.status_code == 404
    assert "X-Request-ID" in response.headers


def test_failed_job_reports_error(client, tmp_path):
    class BrokenService:
        def process_video(self, *args, **kwargs):
            raise RuntimeError("decoder crashed")

    upload_dir = install_job_service(
        client,
        tmp_path,
        processing_service_factory=BrokenService,
    )

    response = client.post(
        "/api/v1/videos/process",
        files={"file": ("broken.mp4", b"data", "video/mp4")},
    )
    processing_id = response.json()["processing_id"]

    status_result = client.get(
        f"/api/v1/videos/{processing_id}/status"
    ).json()

    assert status_result["status"] == "failed"
    assert status_result["error"] == "decoder crashed"
    assert list(upload_dir.iterdir()) == []

    output_response = client.get(f"/api/v1/videos/{processing_id}/output")
    assert output_response.status_code == 409
