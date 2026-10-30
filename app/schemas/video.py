from pydantic import BaseModel

from app.schemas.violation import ViolationResponse


class VideoProcessingResponse(BaseModel):
    """Return video processing results and detected violations."""

    filename: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int
    violations_saved: int
    violations: list[ViolationResponse]
