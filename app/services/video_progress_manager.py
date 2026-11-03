
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class VideoJob:
    processing_id: str
    filename: str
    status: str = "queued"
    processed_frames: int = 0
    total_frames: int = 0
    progress_percent: float = 0.0
    error: str | None = None
    result: dict | None = None


class VideoProgressManager:
    """Thread-safe in-memory storage for video processing jobs."""

    def __init__(self):
        self._jobs: dict[str, VideoJob] = {}
        self._lock = Lock()

    def create(self, processing_id: str, filename: str) -> VideoJob:
        job = VideoJob(
            processing_id=processing_id,
            filename=filename,
        )
        with self._lock:
            self._jobs[processing_id] = job
        return job

    def get(self, processing_id: str) -> VideoJob | None:
        with self._lock:
            return self._jobs.get(processing_id)

    def update(self, processing_id: str, **changes) -> None:
        with self._lock:
            job = self._jobs.get(processing_id)
            if job is None:
                return

            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, value)


video_progress_manager = VideoProgressManager()
