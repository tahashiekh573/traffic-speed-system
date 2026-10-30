from pathlib import Path

import cv2
import numpy as np


class VideoClient:
    """OpenCV wrapper for reading video files frame by frame."""

    def __init__(self, video_path: str | Path) -> None:
        self.video_path = Path(video_path)
        self._capture: cv2.VideoCapture | None = None
        self._frame_index = -1

    def open(self) -> None:
        """Open the video file and initialize its reader."""

        if not self.video_path.is_file():
            raise FileNotFoundError(
                f"Video file not found: {self.video_path}"
            )

        if self._capture is not None:
            self.release()

        capture = cv2.VideoCapture(str(self.video_path))

        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"Unable to open video: {self.video_path}"
            )

        self._capture = capture
        self._frame_index = -1

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next frame from the video."""

        if self._capture is None or not self._capture.isOpened():
            raise RuntimeError("Video is not open. Call open() first.")

        success, frame = self._capture.read()

        if not success:
            return False, None

        self._frame_index += 1
        return True, frame

    @property
    def fps(self) -> float:
        """Return the video's frames per second."""
        return self._get_metadata(cv2.CAP_PROP_FPS)

    @property
    def width(self) -> int:
        """Return the video frame width."""
        return int(self._get_metadata(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        """Return the video frame height."""
        return int(self._get_metadata(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def frame_count(self) -> int:
        """Return the total number of video frames."""
        return int(self._get_metadata(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def frame_index(self) -> int:
        """Return the index of the most recently read frame."""
        return self._frame_index

    @property
    def timestamp_seconds(self) -> float:
        """Return the timestamp of the most recently read frame."""
        if self.fps <= 0 or self._frame_index < 0:
            return 0.0

        return self._frame_index / self.fps

    def _get_metadata(self, property_id: int) -> float:
        """Read video metadata safely."""
        if self._capture is None or not self._capture.isOpened():
            raise RuntimeError("Video is not open.")

        return float(self._capture.get(property_id))

    def release(self) -> None:
        """Release video capture resources."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoClient":
        """Support context manager usage."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Release resources when leaving the context."""
        self.release()
