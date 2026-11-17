"""Schemas for video upload, processing status and final results."""

from pydantic import BaseModel, Field

from app.schemas.violation import ViolationResponse


class PlateRecognitionResponse(BaseModel):
    """Recognized vehicle number plate details."""

    track_id: int
    plate_number: str


class SpeedRecordResponse(BaseModel):
    """Speed measured for one tracked vehicle."""

    track_id: int
    speed_kmh: float
    is_overspeeding: bool
    vehicle_type: str | None = None
    plate_number: str | None = None


class VideoProcessingResponse(BaseModel):
    """Final video processing result."""

    filename: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int
    duration_seconds: float = 0.0
    processing_seconds: float = 0.0
    speed_limit_kmh: float = 0.0

    violations_saved: int
    violations: list[ViolationResponse]

    # Vehicle tracking and speed results
    vehicles_tracked: int = 0
    vehicle_types: dict[str, int] = Field(default_factory=dict)
    speed_records: list[SpeedRecordResponse] = Field(default_factory=list)
    average_speed_kmh: float | None = None
    max_speed_kmh: float | None = None

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
