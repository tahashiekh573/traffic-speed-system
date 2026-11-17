"""Business logic for uploaded video jobs.

Saves uploads, runs the computer vision pipeline in the background,
persists overspeeding violations and builds the final job result.
"""

import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from typing import Any, BinaryIO
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    EmptyVideoUploadError,
    JobNotReadyError,
    ResourceNotFoundError,
    UnsupportedVideoFormatError,
    VideoUploadTooLargeError,
)
from app.core.logging import get_logger
from app.repositories.violation_repository import ViolationRepository
from app.schemas.video import (
    PlateRecognitionResponse,
    SpeedRecordResponse,
    VideoProcessingResponse,
)
from app.schemas.violation import ViolationResponse
from app.services.video_processing_service import VideoProcessingService
from app.services.video_progress_manager import VideoJob, VideoProgressManager

logger = get_logger(__name__)

UPLOAD_CHUNK_SIZE = 1024 * 1024

BackgroundRunner = Callable[[Callable[..., None], tuple], None]


def run_in_daemon_thread(target: Callable[..., None], args: tuple) -> None:
    """Run a job in a daemon thread so uploads return immediately."""
    Thread(target=target, args=args, daemon=True).start()


def _value(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dataclass-like object or a dictionary."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _JobResultCollector:
    """Accumulate per-frame pipeline output into a final job result."""

    def __init__(
        self,
        repository: ViolationRepository,
        speed_limit_kmh: float,
        video_source: str,
    ) -> None:
        self.repository = repository
        self.speed_limit_kmh = speed_limit_kmh
        self.video_source = video_source

        self.vehicle_types: dict[int, str] = {}
        self.plates: dict[int, str] = {}
        self.speeds: dict[int, tuple[float, bool]] = {}
        self.violations: dict[int, ViolationResponse] = {}

    def on_frame(self, output: Any) -> None:
        """Handle the orchestrator output of one frame."""
        for track in _value(output, "tracks", []) or []:
            track_id = int(_value(track, "track_id", 0))
            class_name = _value(track, "class_name")
            if track_id > 0 and class_name:
                self.vehicle_types.setdefault(track_id, str(class_name))

        plate_output = _value(output, "plate_output")
        for reading in _value(plate_output, "readings", []) or []:
            self._record_plate(int(reading.track_id), str(reading.plate_text))

        speed_output = _value(output, "speed_output")
        for measurement in _value(speed_output, "measurements", []) or []:
            self._record_speed(measurement)

    def _record_plate(self, track_id: int, plate: str) -> None:
        self.plates[track_id] = plate

        # The plate is often readable only after the vehicle crossed
        # the speed lines, so back-fill violations that have no plate.
        violation = self.violations.get(track_id)
        if violation is not None and violation.plate_number is None:
            updated = self.repository.update_plate(violation.id, plate)
            if updated is not None:
                self.violations[track_id] = ViolationResponse.model_validate(
                    updated
                )

    def _record_speed(self, measurement: Any) -> None:
        track_id = int(measurement.track_id)
        speed = float(measurement.speed_kmh)
        overspeeding = bool(measurement.is_overspeeding)

        self.speeds[track_id] = (speed, overspeeding)

        if not overspeeding or track_id <= 0 or track_id in self.violations:
            return

        violation = self.repository.create(
            track_id=track_id,
            plate_number=self.plates.get(track_id),
            speed_kmh=speed,
            speed_limit_kmh=self.speed_limit_kmh,
            video_source=self.video_source,
        )
        self.violations[track_id] = ViolationResponse.model_validate(violation)

    def build_response(
        self,
        *,
        result: Any,
        processing_id: str,
        processing_seconds: float,
    ) -> VideoProcessingResponse:
        """Create the API result for a finished job."""
        speed_records = [
            SpeedRecordResponse(
                track_id=track_id,
                speed_kmh=speed,
                is_overspeeding=overspeeding,
                vehicle_type=self.vehicle_types.get(track_id),
                plate_number=self.plates.get(track_id),
            )
            for track_id, (speed, overspeeding) in sorted(self.speeds.items())
        ]
        speeds = [record.speed_kmh for record in speed_records]

        fps = float(result.fps)
        total_frames = int(result.total_frames)

        return VideoProcessingResponse(
            filename=self.video_source,
            fps=fps,
            width=result.width,
            height=result.height,
            total_frames=total_frames,
            processed_frames=result.processed_frames,
            duration_seconds=round(total_frames / fps, 2) if fps > 0 else 0.0,
            processing_seconds=round(processing_seconds, 2),
            speed_limit_kmh=self.speed_limit_kmh,
            violations_saved=len(self.violations),
            violations=list(self.violations.values()),
            vehicles_tracked=len(self.vehicle_types),
            vehicle_types=dict(Counter(self.vehicle_types.values())),
            speed_records=speed_records,
            average_speed_kmh=(
                round(sum(speeds) / len(speeds), 2) if speeds else None
            ),
            max_speed_kmh=round(max(speeds), 2) if speeds else None,
            plates_identified=len(self.plates),
            recognized_plates=[
                PlateRecognitionResponse(track_id=track_id, plate_number=plate)
                for track_id, plate in sorted(self.plates.items())
            ],
            output_video_url=f"/api/v1/videos/{processing_id}/output",
        )


class VideoJobService:
    """Manage the lifecycle of uploaded video processing jobs."""

    def __init__(
        self,
        settings: Settings,
        progress_manager: VideoProgressManager,
        session_factory: Callable[[], Session],
        processing_service_factory: Callable[
            [], VideoProcessingService
        ] = VideoProcessingService,
        background_runner: BackgroundRunner = run_in_daemon_thread,
    ) -> None:
        self.settings = settings
        self.progress_manager = progress_manager
        self.session_factory = session_factory
        self.processing_service_factory = processing_service_factory
        self.background_runner = background_runner

    # ------------------------------------------------------------------
    # Upload handling
    # ------------------------------------------------------------------
    def validate_filename(self, filename: str | None) -> tuple[str, str]:
        """Return the safe base filename and its extension."""
        original = Path(filename or "").name

        if not original:
            raise EmptyVideoUploadError("A video filename is required.")

        extension = Path(original).suffix.lower()

        if extension not in self.settings.video_extensions:
            allowed = ", ".join(sorted(self.settings.video_extensions))
            raise UnsupportedVideoFormatError(
                f"Unsupported video format. Allowed: {allowed}"
            )

        return original, extension

    def _save_upload(self, stream: BinaryIO, destination: Path) -> None:
        """Stream the upload to disk while enforcing the size limit."""
        limit = self.settings.max_upload_size_bytes
        total = 0

        with destination.open("wb") as output:
            while chunk := stream.read(UPLOAD_CHUNK_SIZE):
                total += len(chunk)

                if total > limit:
                    raise VideoUploadTooLargeError(
                        "Video upload exceeds the "
                        f"{self.settings.max_upload_size_mb} MB limit."
                    )

                output.write(chunk)

        if total == 0:
            raise EmptyVideoUploadError("Uploaded video is empty.")

    def start_job(self, filename: str | None, stream: BinaryIO) -> VideoJob:
        """Validate and store an upload, then process it in the background."""
        original, extension = self.validate_filename(filename)

        upload_dir = self.settings.resolved_upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        processing_id = uuid4().hex
        video_path = upload_dir / f"{processing_id}{extension}"

        try:
            self._save_upload(stream, video_path)
        except Exception:
            video_path.unlink(missing_ok=True)
            raise

        job = self.progress_manager.create(processing_id, original)
        logger.info("Queued video job %s for %s", processing_id, original)

        self.background_runner(
            self.run_job,
            (processing_id, video_path, original),
        )

        return self.progress_manager.get(processing_id) or job

    # ------------------------------------------------------------------
    # Background processing
    # ------------------------------------------------------------------
    def output_path_for(self, processing_id: str) -> Path:
        """Return where the annotated video of a job is stored."""
        return self.settings.resolved_output_dir / f"{processing_id}.mp4"

    def run_job(
        self,
        processing_id: str,
        video_path: Path,
        original_filename: str,
    ) -> None:
        """Process a stored upload and record its result in the job store."""
        db = self.session_factory()
        output_path = self.output_path_for(processing_id)
        started = time.perf_counter()

        try:
            self.progress_manager.update(processing_id, status="processing")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            collector = _JobResultCollector(
                repository=ViolationRepository(db),
                speed_limit_kmh=float(self.settings.speed_limit_kmh),
                video_source=original_filename,
            )

            def on_progress(progress: Any) -> None:
                self.progress_manager.update(
                    processing_id,
                    processed_frames=progress.processed_frames,
                    total_frames=progress.total_frames,
                    progress_percent=progress.progress_percent,
                )

            result = self.processing_service_factory().process_video(
                video_path,
                output_video_path=output_path,
                on_frame_processed=collector.on_frame,
                on_progress=on_progress,
            )

            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError("Annotated output video was not generated.")

            response = collector.build_response(
                result=result,
                processing_id=processing_id,
                processing_seconds=time.perf_counter() - started,
            )

            self.progress_manager.update(
                processing_id,
                status="completed",
                processed_frames=result.processed_frames,
                total_frames=result.total_frames,
                progress_percent=100.0,
                result=response.model_dump(mode="json"),
            )
            logger.info(
                "Job %s completed: %s violations, %s plates",
                processing_id,
                response.violations_saved,
                response.plates_identified,
            )

        except Exception as exc:
            logger.exception("Job %s failed", processing_id)
            db.rollback()
            output_path.unlink(missing_ok=True)
            self.progress_manager.update(
                processing_id,
                status="failed",
                error=str(exc),
            )

        finally:
            db.close()
            video_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_job(self, processing_id: str) -> VideoJob:
        """Return a job or raise when it does not exist."""
        job = self.progress_manager.get(processing_id)

        if job is None:
            raise ResourceNotFoundError("Processing job not found.")

        return job

    def get_output_video(self, processing_id: str) -> Path:
        """Return the annotated video path of a completed job."""
        job = self.get_job(processing_id)

        if job.status != "completed":
            raise JobNotReadyError("Video processing is not completed yet.")

        output_path = self.output_path_for(processing_id)

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise ResourceNotFoundError("Processed video file not found or empty.")

        return output_path
