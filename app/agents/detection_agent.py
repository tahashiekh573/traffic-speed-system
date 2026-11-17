"""Vehicle detection agent built on a YOLOv8 detector client."""

from dataclasses import dataclass

import numpy as np

from app.agents.base_agent import BaseAgent
from app.clients.detector_client import Detection, DetectorClient
from app.clients.yolo_detector_client import YOLODetectorClient
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class DetectionInput:
    """A single frame to detect vehicles in."""

    frame: np.ndarray


@dataclass(frozen=True)
class DetectionOutput:
    """Vehicle detections found in a frame."""

    detections: list[Detection]


class DetectionAgent(BaseAgent[DetectionInput, DetectionOutput]):
    """Detect only traffic vehicles (classes come from VEHICLE_CLASSES)."""

    def __init__(
        self,
        detector: DetectorClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detector = detector or YOLODetectorClient(self.settings)
        self.allowed_classes = self.settings.vehicle_class_names

    def run(self, data: DetectionInput) -> DetectionOutput:
        """Run detection and keep only configured vehicle classes."""
        detections = self.detector.detect(data.frame)

        filtered = [
            detection
            for detection in detections
            if detection.class_name.lower() in self.allowed_classes
        ]

        return DetectionOutput(detections=filtered)
