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
from app.core.dependencies import get_frame_orchestrator
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


@dataclass(frozen=True)
class LiveSnapshot:
    """Latest annotated frame and running counts while a video is processed."""

    frame: object  # annotated BGR numpy image
    vehicles_seen: int
    violations: int
    plates: int
    timestamp_seconds: float
    no_helmet: int = 0


class VideoProcessingService:
    """Process videos, annotate vehicles and save browser-compatible MP4."""

    def __init__(
        self,
        orchestrator: FrameOrchestrator | None = None,
        video_client_factory: Callable | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.orchestrator = orchestrator or get_frame_orchestrator()
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
        no_helmet: int | None = None,
    ):
        """Draw a translucent summary banner in the top-right corner."""
        lines = [
            f"LIMIT {speed_limit_kmh:.0f} KM/H",
            f"VEHICLES {vehicles_seen}",
            f"VIOLATIONS {violations}",
        ]
        if no_helmet is not None:
            lines.append(f"NO HELMET {no_helmet}")
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
            alert = (index == 2 and violations > 0) or (index == 3 and bool(no_helmet))
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
        scale: float = 1.0,
    ):
        """Draw speed lines, vehicle boxes, speeds and plates on a frame.

        ``scale`` maps original-video coordinates onto a resized frame.
        """
        settings = settings or get_settings()
        plate_states = plate_states or {}

        # Lines are defined on the original frame; this frame may be resized.
        original_height = frame.shape[0] / scale if scale else frame.shape[0]
        row_1, row_2 = settings.line_rows(int(round(original_height)))
        line_1 = int(row_1 * scale)
        line_2 = int(row_2 * scale)

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

            x1, y1, x2, y2 = (int(value * scale) for value in bbox)

            track_id = VideoProcessingService._get_value(
                track,
                "track_id",
            )

            state = speed_states.get(track_id, {})
            overspeed = state.get("overspeed", False)
            no_helmet = state.get("no_helmet", False)
            speed = state.get("speed")

            color = (
                (0, 0, 255)
                if overspeed or no_helmet
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

            if no_helmet:
                label += " NO HELMET"
            elif state.get("helmet_checked"):
                label += " HELMET OK"

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
            font_scale = 0.55
            thickness = 2

            (text_width, text_height), baseline = (
                cv2.getTextSize(
                    label,
                    font,
                    font_scale,
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
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

        return frame

    def _fit_output(self, frame):
        """Downscale annotated frames so writing and encoding stay fast."""
        max_width = self.settings.output_max_width
        if not max_width or frame.shape[1] <= max_width:
            return frame
        scale = max_width / frame.shape[1]
        size = (max_width, int(round(frame.shape[0] * scale / 2)) * 2)
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

    def process_video(
        self,
        video_path: str | Path,
        on_frame_processed: Callable | None = None,
        on_progress: Callable | None = None,
        output_video_path: str | Path | None = None,
        on_live_snapshot: Callable[[LiveSnapshot], None] | None = None,
    ) -> VideoProcessingResult:
        """Run the pipeline every few frames, annotate all frames, write MP4.

        Only every ``frame_stride``-th frame goes through the vision agents
        (TARGET_PROCESS_FPS). The frames in between are written with the
        latest annotations, which keeps the video smooth at a fraction of
        the cost. Speed accuracy is kept by the SpeedAgent's interpolation.
        """
        client = self.video_client_factory(video_path)
        writer = None

        output_path = Path(output_video_path) if output_video_path else None
        temporary_path = (
            output_path.with_name(f"{output_path.stem}_opencv_temp.mp4")
            if output_path
            else None
        )

        reset = getattr(self.orchestrator, "reset", None)
        if callable(reset):
            reset()

        speed_states: dict = {}
        plate_states: dict[int, str] = {}
        seen_tracks: set[int] = set()
        speed_limit = float(self.settings.speed_limit_kmh)
        completed = False
        last_output = None
        next_snapshot_at = 0.0

        try:
            with client as video:
                fps = video.fps

                if not isfinite(fps) or fps <= 0:
                    raise ValueError("Video FPS must be positive.")

                width = video.width
                height = video.height
                total_frames = video.frame_count
                stride = self.settings.frame_stride(fps)

                frame_index = 0
                analysed_frames = 0

                if on_progress:
                    on_progress(
                        VideoProcessingProgress(0, total_frames, 0.0, "processing")
                    )

                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    if frame is None:
                        raise RuntimeError("Empty video frame.")

                    if frame_index % stride == 0:
                        output = self.orchestrator.process_frame(
                            FrameProcessingInput(
                                frame=frame,
                                timestamp_seconds=video.timestamp_seconds,
                                frame_index=frame_index,
                            )
                        )
                        last_output = output
                        analysed_frames += 1
                        self._collect_states(
                            output, speed_states, plate_states, seen_tracks
                        )

                        if on_frame_processed:
                            on_frame_processed(output)

                    timestamp = video.timestamp_seconds
                    snapshot_due = bool(on_live_snapshot) and (
                        timestamp >= next_snapshot_at
                    )

                    if output_path or snapshot_due:
                        annotated = self._annotate(
                            frame,
                            last_output,
                            speed_states,
                            plate_states,
                            seen_tracks,
                            speed_limit,
                        )

                        if output_path and temporary_path:
                            annotated_out = annotated
                            if writer is None:
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                out_h, out_w = annotated_out.shape[:2]
                                writer = cv2.VideoWriter(
                                    str(temporary_path),
                                    cv2.VideoWriter_fourcc(*"mp4v"),
                                    fps,
                                    (out_w, out_h),
                                )
                                if not writer.isOpened():
                                    raise RuntimeError(
                                        "Unable to create annotated output video."
                                    )
                            writer.write(annotated_out)

                        if snapshot_due:
                            next_snapshot_at = (
                                timestamp + self.settings.preview_interval_seconds
                            )
                            on_live_snapshot(
                                LiveSnapshot(
                                    frame=annotated,
                                    vehicles_seen=len(seen_tracks),
                                    violations=self._violation_count(speed_states),
                                    plates=len(plate_states),
                                    no_helmet=self._no_helmet_count(speed_states),
                                    timestamp_seconds=timestamp,
                                )
                            )

                    frame_index += 1

                    if on_progress:
                        percentage = (
                            min(frame_index / total_frames * 100, 100)
                            if total_frames > 0
                            else 0.0
                        )
                        on_progress(
                            VideoProcessingProgress(
                                frame_index,
                                total_frames,
                                round(percentage, 2),
                                "processing",
                            )
                        )

                if frame_index == 0 or analysed_frames == 0:
                    raise ValueError("No video frames were processed.")

            completed = True

        finally:
            if writer is not None:
                writer.release()

            if not completed and temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        if output_path and temporary_path:
            try:
                self.convert_to_h264(temporary_path, output_path)
            finally:
                temporary_path.unlink(missing_ok=True)

        return VideoProcessingResult(
            video_path=str(Path(video_path)),
            fps=fps,
            width=width,
            height=height,
            total_frames=total_frames,
            processed_frames=frame_index,
            output_video_path=str(output_path) if output_path else None,
        )

    @staticmethod
    def _violation_count(speed_states: dict) -> int:
        """Vehicles with at least one violation (overspeed or no helmet)."""
        return sum(
            1
            for state in speed_states.values()
            if state.get("overspeed") or state.get("no_helmet")
        )

    @staticmethod
    def _no_helmet_count(speed_states: dict) -> int:
        return sum(1 for state in speed_states.values() if state.get("no_helmet"))

    def _collect_states(
        self,
        output,
        speed_states: dict,
        plate_states: dict[int, str],
        seen_tracks: set[int],
    ) -> None:
        """Remember speeds, plates and IDs for drawing later frames."""
        plate_output = self._get_value(output, "plate_output")
        for reading in self._get_value(plate_output, "readings", []) or []:
            plate_states[reading.track_id] = reading.plate_text

        for track in self._get_value(output, "tracks", []) or []:
            seen_tracks.add(self._get_value(track, "track_id"))

        speed_output = self._get_value(output, "speed_output")
        for measurement in self._get_value(speed_output, "measurements", []) or []:
            track_id = self._get_value(measurement, "track_id")
            state = speed_states.setdefault(track_id, {})
            state["speed"] = self._get_value(measurement, "speed_kmh")
            state["overspeed"] = self._get_value(measurement, "is_overspeeding", False)

        helmet_output = self._get_value(output, "helmet_output")
        for status in self._get_value(helmet_output, "statuses", []) or []:
            state = speed_states.setdefault(status.track_id, {})
            state["helmet_checked"] = True
            state["no_helmet"] = not status.has_helmet

    def _annotate(
        self,
        frame,
        output,
        speed_states: dict,
        plate_states: dict[int, str],
        seen_tracks: set[int],
        speed_limit: float,
    ):
        """Return a resized copy of the frame with boxes, labels and the HUD.

        Drawing on the already-downscaled frame is much cheaper than
        drawing on the full-resolution frame and resizing afterwards.
        """
        annotated = self._fit_output(frame)
        if annotated is frame:
            annotated = frame.copy()
        scale = annotated.shape[1] / frame.shape[1]
        if output is not None:
            self.draw_annotations(
                annotated,
                output,
                speed_states,
                plate_states,
                self.settings,
                scale,
            )
        helmet_enabled = bool(getattr(self.orchestrator, "helmet_check_enabled", False))
        self.draw_hud(
            annotated,
            speed_limit,
            len(seen_tracks),
            self._violation_count(speed_states),
            self._no_helmet_count(speed_states) if helmet_enabled else None,
        )
        return annotated
