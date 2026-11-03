
from pydantic import BaseModel
from app.schemas.violation import ViolationResponse


class VideoProcessingResponse(BaseModel):
    filename: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int
    violations_saved: int
    violations: list[ViolationResponse]
    output_video_url: str | None = None


class VideoProcessingStatusResponse(BaseModel):
    processing_id: str
    filename: str
    status: str
    processed_frames: int
    total_frames: int
    progress_percent: float
    error: str | None = None
    result: VideoProcessingResponse | None = None
