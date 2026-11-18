"""Vehicle tracking agent built on YOLOv8 + ByteTrack."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.agents.base_agent import BaseAgent
from app.clients.yolo_detector_client import YOLODetectorClient
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class TrackingInput:
    """A single frame to track vehicles in."""

    frame: np.ndarray


@dataclass(frozen=True)
class TrackedObject:
    """A vehicle with a persistent ByteTrack identifier."""

    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True)
class TrackingOutput:
    """All vehicles tracked in a frame."""

    tracks: list[TrackedObject]


class TrackingAgent(BaseAgent[TrackingInput, TrackingOutput]):
    """Track vehicles across consecutive frames using ByteTrack."""

    def __init__(
        self,
        detector: YOLODetectorClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detector = detector or YOLODetectorClient(self.settings)
        self.model = self.detector.model
        self.vehicle_classes = self.settings.vehicle_class_names
        self.image_size = getattr(
            self.detector,
            "image_size",
            self.settings.yolo_image_size,
        )

    def reset(self) -> None:
        """Clear ByteTrack state so a new video starts with fresh IDs."""
        predictor = getattr(self.model, "predictor", None)
        for tracker in getattr(predictor, "trackers", None) or []:
            if hasattr(tracker, "reset"):
                tracker.reset()

    @staticmethod
    def _to_list(value: Any) -> list:
        """Convert tensors / arrays to plain Python lists."""
        if value is None:
            return []

        if hasattr(value, "cpu"):
            value = value.cpu()

        if hasattr(value, "tolist"):
            value = value.tolist()

        return value

    def run(self, data: TrackingInput) -> TrackingOutput:
        """Track vehicles in the frame and drop non-vehicle classes."""
        if not isinstance(data.frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        results = self.model.track(
            source=data.frame,
            persist=True,
            tracker="bytetrack.yaml",
            # No conf here on purpose: ByteTrack needs the low-confidence
            # detections (Ultralytics uses 0.1 in track mode) to keep IDs.
            imgsz=self.image_size,
            verbose=False,
        )

        if not results:
            return TrackingOutput(tracks=[])

        boxes = results[0].boxes

        if boxes is None or boxes.id is None:
            return TrackingOutput(tracks=[])

        names = results[0].names
        tracks: list[TrackedObject] = []

        for bbox, confidence, class_id, track_id in zip(
            self._to_list(boxes.xyxy),
            self._to_list(boxes.conf),
            self._to_list(boxes.cls),
            self._to_list(boxes.id),
            strict=False,
        ):
            class_id = int(class_id)
            class_name = str(names[class_id])

            if (
                self.vehicle_classes
                and class_name.lower() not in self.vehicle_classes
            ):
                continue

            tracks.append(
                TrackedObject(
                    track_id=int(track_id),
                    bbox=tuple(float(value) for value in bbox),
                    confidence=float(confidence),
                    class_id=class_id,
                    class_name=class_name,
                )
            )

        return TrackingOutput(tracks=tracks)
