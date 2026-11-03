
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import cv2

from app.core.config import get_settings
from app.clients.video_client import VideoClient
from app.orchestrators.frame_orchestrator import (
    FrameOrchestrator,
    FrameProcessingInput,
)


@dataclass(frozen=True)
class VideoProcessingResult:
    video_path: str
    fps: float
    width: int
    height: int
    total_frames: int
    processed_frames: int
    output_video_path: str | None = None


@dataclass(frozen=True)
class VideoProcessingProgress:
    processed_frames: int
    total_frames: int
    progress_percent: float
    status: str


class VideoProcessingService:
    """Process videos, annotate vehicles and save output MP4."""

    def __init__(
        self,
        orchestrator: FrameOrchestrator | None = None,
        video_client_factory: Callable | None = None,
    ) -> None:
        self.orchestrator = orchestrator or FrameOrchestrator()
        self.video_client_factory = video_client_factory or VideoClient

    @staticmethod
    def draw_annotations(frame, output, speed_states):
        settings = get_settings()

        # Draw speed measurement lines
        line_1 = int(settings.line_1_y)
        line_2 = int(settings.line_2_y)

        cv2.line(
            frame, (0, line_1), (frame.shape[1], line_1),
            (255, 255, 0), 2
        )
        cv2.line(
            frame, (0, line_2), (frame.shape[1], line_2),
            (0, 255, 255), 2
        )

        cv2.putText(
            frame, "SPEED LINE 1", (10, max(20, line_1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
        )
        cv2.putText(
            frame, "SPEED LINE 2", (10, max(20, line_2 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
        )

        for track in output.tracks:
            x1, y1, x2, y2 = map(int, track.bbox)

            state = speed_states.get(track.track_id, {})
            overspeed = state.get("overspeed", False)
            speed = state.get("speed")

            color = (0, 0, 255) if overspeed else (0, 220, 100)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = (
                f"{track.class_name.upper()} "
                f"ID:{track.track_id} "
                f"{track.confidence:.2f}"
            )

            if speed is not None:
                label += f" {speed:.1f} km/h"

            if overspeed:
                label += " OVERSPEED"

            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.55
            thickness = 2

            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, scale, thickness
            )

            top = max(0, y1 - text_height - baseline - 8)

            cv2.rectangle(
                frame,
                (x1, top),
                (x1 + text_width + 8, y1),
                color,
                -1,
            )

            cv2.putText(
                frame,
                label,
                (x1 + 4, max(text_height, y1 - baseline - 4)),
                font,
                scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

        return frame

    def process_video(
        self,
        video_path: str | Path,
        on_frame_processed: Callable | None = None,
        on_progress: Callable | None = None,
        output_video_path: str | Path | None = None,
    ) -> VideoProcessingResult:

        client = self.video_client_factory(video_path)
        writer = None
        output_path = Path(output_video_path) if output_video_path else None
        speed_states = {}

        try:
            with client as video:
                fps = video.fps

                if not isfinite(fps) or fps <= 0:
                    raise ValueError("Video FPS must be positive.")

                width = video.width
                height = video.height
                total_frames = video.frame_count
                processed_frames = 0
                frame_index = 0

                if output_path:
                    output_path.parent.mkdir(
                        parents=True, exist_ok=True
                    )

                    writer = cv2.VideoWriter(
                        str(output_path),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (width, height),
                    )

                    if not writer.isOpened():
                        raise RuntimeError(
                            "Unable to create annotated output video."
                        )

                if on_progress:
                    on_progress(
                        VideoProcessingProgress(
                            0, total_frames, 0.0, "processing"
                        )
                    )

                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    if frame is None:
                        raise RuntimeError("Empty video frame.")

                    output = self.orchestrator.process_frame(
                        FrameProcessingInput(
                            frame=frame,
                            timestamp_seconds=video.timestamp_seconds,
                            frame_index=frame_index,
                        )
                    )

                    for measurement in output.speed_output.measurements:
                        speed_states[measurement.track_id] = {
                            "speed": measurement.speed_kmh,
                            "overspeed": measurement.is_overspeeding,
                        }

                    annotated_frame = self.draw_annotations(
                        frame.copy(), output, speed_states
                    )

                    if writer is not None:
                        writer.write(annotated_frame)

                    if on_frame_processed:
                        on_frame_processed(output)

                    processed_frames += 1
                    frame_index += 1

                    if on_progress:
                        percentage = (
                            min(processed_frames / total_frames * 100, 100)
                            if total_frames > 0 else 0.0
                        )

                        on_progress(
                            VideoProcessingProgress(
                                processed_frames,
                                total_frames,
                                round(percentage, 2),
                                "processing",
                            )
                        )

                if processed_frames == 0:
                    raise ValueError("No video frames were processed.")

            return VideoProcessingResult(
                video_path=str(Path(video_path)),
                fps=fps,
                width=width,
                height=height,
                total_frames=total_frames,
                processed_frames=processed_frames,
                output_video_path=str(output_path) if output_path else None,
            )

        finally:
            if writer is not None:
                writer.release()
