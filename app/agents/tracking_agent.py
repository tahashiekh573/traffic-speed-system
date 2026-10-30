from dataclasses import dataclass

import numpy as np

from app.agents.base_agent import BaseAgent
from app.clients.yolo_detector_client import YOLODetectorClient


@dataclass(frozen=True)
class TrackingInput:
    frame: np.ndarray


@dataclass(frozen=True)
class TrackedObject:
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True)
class TrackingOutput:
    tracks: list[TrackedObject]


class TrackingAgent(BaseAgent[TrackingInput, TrackingOutput]):
    """Track vehicles across consecutive frames using ByteTrack."""

    def __init__(self, detector: YOLODetectorClient | None = None):
        self.detector = detector or YOLODetectorClient()
        self.model = self.detector.model

    @staticmethod
    def _to_list(value):
        if value is None:
            return []

        if hasattr(value, "cpu"):
            value = value.cpu()

        if hasattr(value, "tolist"):
            value = value.tolist()

        return value

    def run(self, data: TrackingInput) -> TrackingOutput:
        if not isinstance(data.frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        results = self.model.track(
            source=data.frame,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )

        if not results:
            return TrackingOutput(tracks=[])

        boxes = results[0].boxes

        if boxes is None or boxes.id is None:
            return TrackingOutput(tracks=[])

        coordinates = self._to_list(boxes.xyxy)
        confidences = self._to_list(boxes.conf)
        class_ids = self._to_list(boxes.cls)
        track_ids = self._to_list(boxes.id)

        names = results[0].names
        tracks = []

        for bbox, confidence, class_id, track_id in zip(
            coordinates,
            confidences,
            class_ids,
            track_ids,
            strict=False,
        ):
            class_id = int(class_id)

            tracks.append(
                TrackedObject(
                    track_id=int(track_id),
                    bbox=tuple(float(value) for value in bbox),
                    confidence=float(confidence),
                    class_id=class_id,
                    class_name=names[class_id],
                )
            )

        return TrackingOutput(tracks=tracks)

