
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.violation_repository import ViolationRepository
from app.schemas.video import (
    VideoProcessingResponse,
    VideoProcessingStatusResponse,
)
from app.schemas.violation import ViolationResponse
from app.services.video_processing_service import VideoProcessingService
from app.services.video_progress_manager import video_progress_manager

router = APIRouter(
    prefix="/api/v1/videos",
    tags=["Videos"],
)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


def process_video_background(
    processing_id: str,
    video_path: Path,
    original_filename: str,
) -> None:
    """Process video in a background thread and save annotated output."""

    db: Session = SessionLocal()
    output_path: Path | None = None

    try:
        video_progress_manager.update(processing_id, status="processing")

        settings = get_settings()
        repository = ViolationRepository(db)

        output_dir = settings.resolve_path(Path("data/outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{processing_id}.mp4"

        latest_plates: dict[int, str] = {}
        saved_violations: list[ViolationResponse] = []

        def on_frame_processed(output) -> None:
            for reading in output.plate_output.readings:
                latest_plates[reading.track_id] = reading.plate_text

            for measurement in output.speed_output.measurements:
                if not measurement.is_overspeeding:
                    continue

                if measurement.track_id <= 0:
                    continue

                violation = repository.create(
                    track_id=measurement.track_id,
                    plate_number=latest_plates.get(measurement.track_id),
                    speed_kmh=measurement.speed_kmh,
                    speed_limit_kmh=float(settings.speed_limit_kmh),
                    violation_time=datetime.utcnow(),
                    video_source=original_filename,
                )

                saved_violations.append(
                    ViolationResponse.model_validate(violation)
                )

        def on_progress(progress) -> None:
            video_progress_manager.update(
                processing_id,
                processed_frames=progress.processed_frames,
                total_frames=progress.total_frames,
                progress_percent=progress.progress_percent,
            )

        result = VideoProcessingService().process_video(
            video_path,
            output_video_path=output_path,
            on_frame_processed=on_frame_processed,
            on_progress=on_progress,
        )

        db.commit()

        response = VideoProcessingResponse(
            filename=original_filename,
            fps=result.fps,
            width=result.width,
            height=result.height,
            total_frames=result.total_frames,
            processed_frames=result.processed_frames,
            violations_saved=len(saved_violations),
            violations=saved_violations,
            output_video_url=f"/api/v1/videos/{processing_id}/output",
        )

        video_progress_manager.update(
            processing_id,
            status="completed",
            processed_frames=result.processed_frames,
            total_frames=result.total_frames,
            progress_percent=100.0,
            result=response.model_dump(mode="json"),
        )

    except Exception as exc:
        db.rollback()

        if output_path is not None and output_path.exists():
            output_path.unlink()

        video_progress_manager.update(
            processing_id,
            status="failed",
            error=str(exc),
        )

    finally:
        db.close()

        if video_path.exists():
            video_path.unlink()


@router.post(
    "/process",
    response_model=VideoProcessingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_uploaded_video(
    file: Annotated[UploadFile, File(...)],
):
    """Upload a video and start background processing."""

    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A video filename is required.",
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported video format.",
        )

    settings = get_settings()
    upload_dir = settings.resolve_path(Path("data/videos"))
    upload_dir.mkdir(parents=True, exist_ok=True)

    processing_id = uuid4().hex
    video_path = upload_dir / f"{processing_id}{extension}"
    total_bytes = 0

    try:
        with video_path.open("wb") as destination:
            while True:
                chunk = file.file.read(UPLOAD_CHUNK_SIZE)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Video upload exceeds the 500 MB limit.",
                    )

                destination.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video is empty.",
            )

        video_progress_manager.create(
            processing_id,
            original_filename,
        )

        worker = Thread(
            target=process_video_background,
            args=(processing_id, video_path, original_filename),
            daemon=True,
        )
        worker.start()

        job = video_progress_manager.get(processing_id)

        return VideoProcessingStatusResponse(
            processing_id=processing_id,
            filename=original_filename,
            status=job.status,
            processed_frames=job.processed_frames,
            total_frames=job.total_frames,
            progress_percent=job.progress_percent,
        )

    except HTTPException:
        if video_path.exists():
            video_path.unlink()
        raise

    except Exception as exc:
        if video_path.exists():
            video_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start video processing.",
        ) from exc

    finally:
        file.file.close()


@router.get(
    "/{processing_id}/status",
    response_model=VideoProcessingStatusResponse,
)
def get_video_processing_status(processing_id: str):
    """Get progress and results for a processing job."""

    job = video_progress_manager.get(processing_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found.",
        )

    return VideoProcessingStatusResponse(
        processing_id=job.processing_id,
        filename=job.filename,
        status=job.status,
        processed_frames=job.processed_frames,
        total_frames=job.total_frames,
        progress_percent=job.progress_percent,
        error=job.error,
        result=job.result,
    )


@router.get("/{processing_id}/output")
def get_processed_video(processing_id: str):
    """Return the annotated video for a completed job."""

    job = video_progress_manager.get(processing_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found.",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video processing is not completed yet.",
        )

    settings = get_settings()
    output_dir = settings.resolve_path(Path("data/outputs"))
    output_path = output_dir / f"{processing_id}.mp4"

    if not output_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processed video file not found.",
        )

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=f"{processing_id}_annotated.mp4",
    )
