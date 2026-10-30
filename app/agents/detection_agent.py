from dataclasses import dataclass

import numpy as np

from app.agents.base_agent import BaseAgent
from app.clients.detector_client import Detection
from app.clients.yolo_detector_client import YOLODetectorClient


@dataclass(frozen=True)
class DetectionInput:
    frame: np.ndarray


@dataclass(frozen=True)
class DetectionOutput:
    detections: list[Detection]


class DetectionAgent(BaseAgent[DetectionInput, DetectionOutput]):
    """Detect only traffic vehicles."""

    ALLOWED_CLASSES = {
        "car",
        "motorcycle",
        "bus",
        "truck",
    }

    def __init__(self, detector: YOLODetectorClient | None = None):
        self.detector = detector or YOLODetectorClient()

    def run(self, data: DetectionInput) -> DetectionOutput:
        detections = self.detector.detect(data.frame)

        filtered = [
            detection
            for detection in detections
            if detection.class_name.lower() in self.ALLOWED_CLASSES
        ]

        return DetectionOutput(detections=filtered)
