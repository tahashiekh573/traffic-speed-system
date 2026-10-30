from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.violation_repository import ViolationRepository
from app.schemas.video import VideoProcessingResponse
from app.schemas.violation import ViolationResponse
from app.services.video_processing_service import VideoProcessingService

router = APIRouter(
    prefix="/api/v1/videos",
    tags=["Videos"],
)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


@router.post(
    "/process",
    response_model=VideoProcessingResponse,
    status_code=status.HTTP_200_OK,
)
def process_uploaded_video(
    file: Annotated[UploadFile, File(...)],
    db: Session = Depends(get_db),  # noqa: B008
):
    """Process an uploaded video and persist detected speed violations."""

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

    video_path = upload_dir / f"{uuid4().hex}{extension}"
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

        repository = ViolationRepository(db)
        latest_plates: dict[int, str] = {}
        saved_violations = []

        def save_overspeeding_violations(output) -> None:
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

        service = VideoProcessingService()
        result = service.process_video(
            video_path,
            on_frame_processed=save_overspeeding_violations,
        )

        return VideoProcessingResponse(
            filename=original_filename,
            fps=result.fps,
            width=result.width,
            height=result.height,
            total_frames=result.total_frames,
            processed_frames=result.processed_frames,
            violations_saved=len(saved_violations),
            violations=saved_violations,
        )

    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        if video_path.exists():
            video_path.unlink()

        file.file.close()

