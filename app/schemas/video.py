
from pydantic import BaseModel, Field

from app.schemas.violation import ViolationResponse


class PlateRecognitionResponse(BaseModel):
    """Recognized vehicle number plate details."""

    track_id: int
    plate_number: str


class VideoProcessingResponse(BaseModel):
    """Final video processing result."""

    filename: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int
    violations_saved: int
    violations: list[ViolationResponse]

    # Number plate recognition results
    plates_identified: int = 0
    recognized_plates: list[PlateRecognitionResponse] = Field(
        default_factory=list
    )

    # Annotated video URL
    output_video_url: str | None = None


class VideoProcessingStatusResponse(BaseModel):
    """Video processing status and final result."""

    processing_id: str
    filename: str
    status: str
    processed_frames: int
    total_frames: int
    progress_percent: float
    error: str | None = None
    result: VideoProcessingResponse | None = None
