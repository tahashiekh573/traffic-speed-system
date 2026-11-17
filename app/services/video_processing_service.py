"""Run the frame pipeline over a video and write an annotated MP4."""

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import cv2

from app.clients.video_client import VideoClient
from app.core.config import Settings, get_settings
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
    """Process videos, annotate vehicles and save browser-compatible MP4."""

    def __init__(
        self,
        orchestrator: FrameOrchestrator | None = None,
        video_client_factory: Callable | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.orchestrator = orchestrator or FrameOrchestrator()
        self.video_client_factory = video_client_factory or VideoClient

    @staticmethod
    def find_ffmpeg() -> str:
        """Find FFmpeg from PATH or WinGet installation."""

        ffmpeg = shutil.which("ffmpeg")

        if ffmpeg:
            return ffmpeg

        local_app_data = os.environ.get("LOCALAPPDATA")

        if local_app_data:
            packages_dir = (
                Path(local_app_data)
                / "Microsoft"
                / "WinGet"
                / "Packages"
            )

            candidates = list(
                packages_dir.glob(
                    "Gyan.FFmpeg.Shared*/**/bin/ffmpeg.exe"
                )
            )

            if candidates:
                return str(candidates[0])

        raise FileNotFoundError(
            "FFmpeg not found. Please install FFmpeg."
        )

    @staticmethod
    def convert_to_h264(
        temporary_path: Path,
        final_path: Path,
    ) -> None:
        """Convert OpenCV output to browser-compatible H.264."""

        ffmpeg = VideoProcessingService.find_ffmpeg()

        final_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if final_path.exists():
            final_path.unlink()

        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-threads", "0",
            "-i", str(temporary_path),
            "-map", "0:v:0",
            "-an",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "26",
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=1800,
            )

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "FFmpeg conversion exceeded 30 minutes. "
                "Try a lower-resolution input video."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg H.264 conversion failed:\n"
                + result.stderr[-4000:]
            )

        if (
            not final_path.exists()
            or final_path.stat().st_size == 0
        ):
            raise RuntimeError(
                "H.264 output video was not created."
            )

        temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _get_value(obj, key, default=None):
        """Read a value from either a dictionary or an object."""

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    @staticmethod
    def draw_hud(
        frame,
        speed_limit_kmh: float,
        vehicles_seen: int,
        violations: int,
    ):
        """Draw a translucent summary banner in the top-right corner."""
        lines = [
            f"LIMIT {speed_limit_kmh:.0f} KM/H",
            f"VEHICLES {vehicles_seen}",
            f"VIOLATIONS {violations}",
        ]
        font = cv2.FONT_HERSHEY_SIMPLEX
        width = 230
        height = 24 * len(lines) + 16
        x1 = max(0, frame.shape[1] - width - 12)
        y1 = 12

        overlay = frame.copy()
        cv2.rectangle(
            overlay, (x1, y1), (x1 + width, y1 + height), (20, 16, 12), -1
        )
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        for index, text in enumerate(lines):
            alert = index == 2 and violations > 0
            color = (80, 80, 255) if alert else (230, 230, 230)
            cv2.putText(
                frame,
                text,
                (x1 + 12, y1 + 28 + index * 24),
                font,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        return frame

    @staticmethod
    def draw_annotations(
        frame,
        output,
        speed_states,
        plate_states: dict | None = None,
        settings: Settings | None = None,
    ):
        """Draw speed lines, vehicle boxes, speeds and plates on a frame."""
        settings = settings or get_settings()
        plate_states = plate_states or {}

        line_1 = int(settings.line_1_y)
        line_2 = int(settings.line_2_y)

        cv2.line(
            frame,
            (0, line_1),
            (frame.shape[1], line_1),
            (255, 255, 0),
            2,
        )

        cv2.line(
            frame,
            (0, line_2),
            (frame.shape[1], line_2),
            (0, 255, 255),
            2,
        )

        cv2.putText(
            frame,
            "SPEED LINE 1",
            (10, max(20, line_1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2,
        )

        cv2.putText(
            frame,
            "SPEED LINE 2",
            (10, max(20, line_2 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
        )

        tracks = VideoProcessingService._get_value(
            output,
            "tracks",
            [],
        )

        for track in tracks or []:
            bbox = VideoProcessingService._get_value(
                track,
                "bbox",
            )

            if bbox is None or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = map(int, bbox)

            track_id = VideoProcessingService._get_value(
                track,
                "track_id",
            )

            state = speed_states.get(track_id, {})
            overspeed = state.get("overspeed", False)
            speed = state.get("speed")

            color = (
                (0, 0, 255)
                if overspeed
                else (0, 220, 100)
            )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                2,
            )

            class_name = VideoProcessingService._get_value(
                track,
                "class_name",
                "VEHICLE",
            )

            confidence = VideoProcessingService._get_value(
                track,
                "confidence",
                0.0,
            )

            label = (
                f"{str(class_name).upper()} "
                f"ID:{track_id} "
                f"{float(confidence):.2f}"
            )

            if speed is not None:
                label += f" {speed:.1f} km/h"

            if overspeed:
                label += " OVERSPEED"

            plate = plate_states.get(track_id)
            if plate:
                cv2.putText(
                    frame,
                    f"PLATE {plate}",
                    (x1, min(frame.shape[0] - 6, y2 + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.55
            thickness = 2

            (text_width, text_height), baseline = (
                cv2.getTextSize(
                    label,
                    font,
                    scale,
                    thickness,
                )
            )

            top = max(
                0,
                y1 - text_height - baseline - 8,
            )

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
                (
                    x1 + 4,
                    max(text_height, y1 - baseline - 4),
                ),
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
        """Process every frame, report progress and write the annotated video."""

        client = self.video_client_factory(video_path)
        writer = None

        output_path = (
            Path(output_video_path)
            if output_video_path
            else None
        )

        temporary_path = (
            output_path.with_name(
                f"{output_path.stem}_opencv_temp.mp4"
            )
            if output_path
            else None
        )

        speed_states = {}
        plate_states: dict[int, str] = {}
        seen_tracks: set[int] = set()
        speed_limit = float(self.settings.speed_limit_kmh)
        completed = False

        try:
            with client as video:
                fps = video.fps

                if not isfinite(fps) or fps <= 0:
                    raise ValueError(
                        "Video FPS must be positive."
                    )

                width = video.width
                height = video.height
                total_frames = video.frame_count

                processed_frames = 0
                frame_index = 0

                if output_path and temporary_path:
                    output_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    writer = cv2.VideoWriter(
                        str(temporary_path),
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
                            0,
                            total_frames,
                            0.0,
                            "processing",
                        )
                    )

                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    if frame is None:
                        raise RuntimeError(
                            "Empty video frame."
                        )

                    output = self.orchestrator.process_frame(
                        FrameProcessingInput(
                            frame=frame,
                            timestamp_seconds=video.timestamp_seconds,
                            frame_index=frame_index,
                        )
                    )

                    speed_output = self._get_value(
                        output,
                        "speed_output",
                    )

                    measurements = self._get_value(
                        speed_output,
                        "measurements",
                        [],
                    )

                    plate_output = self._get_value(output, "plate_output")
                    readings = self._get_value(plate_output, "readings", [])
                    for reading in readings or []:
                        plate_states[reading.track_id] = reading.plate_text

                    for track in self._get_value(output, "tracks", []) or []:
                        seen_tracks.add(self._get_value(track, "track_id"))

                    for measurement in measurements or []:
                        track_id = self._get_value(
                            measurement,
                            "track_id",
                        )

                        speed = self._get_value(
                            measurement,
                            "speed_kmh",
                        )

                        overspeed = self._get_value(
                            measurement,
                            "is_overspeeding",
                            False,
                        )

                        speed_states[track_id] = {
                            "speed": speed,
                            "overspeed": overspeed,
                        }

                    if writer is not None:
                        annotated_frame = self.draw_annotations(
                            frame.copy(),
                            output,
                            speed_states,
                            plate_states,
                            self.settings,
                        )
                        violation_count = sum(
                            1
                            for state in speed_states.values()
                            if state.get("overspeed")
                        )
                        self.draw_hud(
                            annotated_frame,
                            speed_limit,
                            len(seen_tracks),
                            violation_count,
                        )
                        writer.write(annotated_frame)

                    if on_frame_processed:
                        on_frame_processed(output)

                    processed_frames += 1
                    frame_index += 1

                    if on_progress:
                        percentage = (
                            min(
                                processed_frames / total_frames * 100,
                                100,
                            )
                            if total_frames > 0
                            else 0.0
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
                    raise ValueError(
                        "No video frames were processed."
                    )

            completed = True

        finally:
            if writer is not None:
                writer.release()

            if not completed and temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        if output_path and temporary_path:
            try:
                self.convert_to_h264(
                    temporary_path,
                    output_path,
                )
            finally:
                temporary_path.unlink(missing_ok=True)

        return VideoProcessingResult(
            video_path=str(Path(video_path)),
            fps=fps,
            width=width,
            height=height,
            total_frames=total_frames,
            processed_frames=processed_frames,
            output_video_path=(
                str(output_path)
                if output_path
                else None
            ),
        )
