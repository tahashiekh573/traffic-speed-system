"""HTTP endpoints for uploading videos and reading processing results."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.exceptions import (
    EmptyVideoUploadError,
    JobNotReadyError,
    ResourceNotFoundError,
    UnsupportedVideoFormatError,
    VideoUploadError,
    VideoUploadTooLargeError,
)
from app.db.session import SessionLocal
from app.schemas.video import VideoProcessingStatusResponse
from app.services.video_job_service import VideoJobService
from app.services.video_progress_manager import VideoJob, video_progress_manager

router = APIRouter(
    prefix="/api/v1/videos",
    tags=["Videos"],
)

UPLOAD_ERROR_STATUS: dict[type[VideoUploadError], int] = {
    UnsupportedVideoFormatError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    VideoUploadTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    EmptyVideoUploadError: status.HTTP_400_BAD_REQUEST,
}


@lru_cache(maxsize=1)
def get_video_job_service() -> VideoJobService:
    """Provide the shared video job service."""
    return VideoJobService(
        settings=get_settings(),
        progress_manager=video_progress_manager,
        session_factory=SessionLocal,
    )


VideoJobServiceDep = Annotated[VideoJobService, Depends(get_video_job_service)]


def _to_status_response(job: VideoJob) -> VideoProcessingStatusResponse:
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


@router.post(
    "/process",
    response_model=VideoProcessingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_uploaded_video(
    file: Annotated[UploadFile, File(...)],
    service: VideoJobServiceDep,
) -> VideoProcessingStatusResponse:
    """Upload a video and start background processing."""
    try:
        job = service.start_job(file.filename, file.file)
    except VideoUploadError as exc:
        raise HTTPException(
            status_code=UPLOAD_ERROR_STATUS.get(
                type(exc), status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store the uploaded video.",
        ) from exc
    finally:
        file.file.close()

    return _to_status_response(job)


@router.get(
    "/{processing_id}/status",
    response_model=VideoProcessingStatusResponse,
)
def get_video_processing_status(
    processing_id: str,
    service: VideoJobServiceDep,
) -> VideoProcessingStatusResponse:
    """Get processing progress and final results."""
    try:
        return _to_status_response(service.get_job(processing_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{processing_id}/output")
def get_processed_video(
    processing_id: str,
    service: VideoJobServiceDep,
) -> FileResponse:
    """Return the generated annotated MP4 video."""
    try:
        output_path = service.get_output_video(processing_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except JobNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=f"{processing_id}_annotated.mp4",
    )
