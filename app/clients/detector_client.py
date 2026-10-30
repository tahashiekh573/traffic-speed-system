from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Detection:
    """Structured result returned by an object detector."""

    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str


class DetectorClient(Protocol):
    """Interface for computer vision object detectors."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect objects in a single video frame."""
        ...
