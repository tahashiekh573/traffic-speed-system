from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from app.clients.video_client import VideoClient
from app.orchestrators.frame_orchestrator import (
    FrameOrchestrator,
    FrameProcessingInput,
    FrameProcessingOutput,
)


@dataclass(frozen=True)
class VideoProcessingResult:
    """Summary of a completed video-processing run."""

    video_path: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int


class VideoProcessingService:
    """Process a video sequentially through the frame orchestrator."""

    def __init__(
        self,
        orchestrator: FrameOrchestrator | None = None,
        video_client_factory: Callable[[str | Path], VideoClient] | None = None,
    ) -> None:
        self.orchestrator = orchestrator or FrameOrchestrator()
        self.video_client_factory = video_client_factory or VideoClient

    def process_video(
        self,
        video_path: str | Path,
        on_frame_processed: (
            Callable[[FrameProcessingOutput], None] | None
        ) = None,
    ) -> VideoProcessingResult:
        """Read and process every frame in a video.

        The optional callback receives each frame's processing output.
        Frames are processed sequentially rather than stored in memory.
        """

        client = self.video_client_factory(video_path)

        with client as video:
            fps = video.fps

            if not isfinite(fps) or fps <= 0:
                raise ValueError(
                    "Video FPS must be a finite positive number."
                )

            width = video.width
            height = video.height
            total_frames = video.frame_count
            processed_frames = 0

            while True:
                success, frame = video.read()

                if not success:
                    break

                if frame is None:
                    raise RuntimeError(
                        "Video reader returned an empty frame."
                    )

                output = self.orchestrator.process_frame(
                    FrameProcessingInput(
                        frame=frame,
                        timestamp_seconds=video.timestamp_seconds,
                    )
                )

                if on_frame_processed is not None:
                    on_frame_processed(output)

                processed_frames += 1

        return VideoProcessingResult(
            video_path=str(Path(video_path)),
            fps=fps,
            width=width,
            height=height,
            total_frames=total_frames,
            processed_frames=processed_frames,
        )
