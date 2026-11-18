"""YOLO wrapper for a helmet / no-helmet detection model."""

from dataclasses import dataclass
from importlib.util import find_spec

import numpy as np

from app.core.config import Settings, get_settings

HELMET = "helmet"
NO_HELMET = "no_helmet"


def _has_module(name: str) -> bool:
    return find_spec(name) is not None


@dataclass(frozen=True)
class HeadDetection:
    """A rider's head found in an image, with or without a helmet."""

    label: str  # HELMET or NO_HELMET
    confidence: float
    bbox: tuple[float, float, float, float]


class HelmetDetectorClient:
    """Run a YOLO helmet model and map its class names to helmet / no helmet.

    Public helmet models name their classes differently ("helmet",
    "With Helmet", "no-helmet", "head", ...). The names are mapped through
    HELMET_CLASS_NAMES / NO_HELMET_CLASS_NAMES; other classes are ignored.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_path = self.settings.resolved_helmet_model_path

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Helmet model not found: {self.model_path}. "
                "Put a YOLO helmet detection model there (see README)."
            )

        # Ultralytics silently pip-installs a missing runtime; fail clearly instead.
        is_onnx = self.model_path.suffix.lower() == ".onnx"
        if is_onnx and not _has_module("onnxruntime"):
            raise ImportError(
                "onnxruntime is required for the ONNX helmet model. Install it with: "
                ".venv/Scripts/python -m pip install onnxruntime"
            )

        from ultralytics import YOLO  # Heavy import, only when used.

        self.model = YOLO(str(self.model_path), task="detect")
        self.helmet_labels = self.settings.helmet_labels
        self.no_helmet_labels = self.settings.no_helmet_labels
        self.class_map = self._build_class_map(self.model.names)

        if not self.class_map:
            raise ValueError(
                "The helmet model has no class matching HELMET_CLASS_NAMES or "
                "NO_HELMET_CLASS_NAMES. Model classes: "
                f"{list(self.model.names.values())}"
            )

    def _build_class_map(self, names: dict[int, str]) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for class_id, name in names.items():
            label = Settings.normalize_label(str(name))
            if label in self.no_helmet_labels:
                mapping[int(class_id)] = NO_HELMET
            elif label in self.helmet_labels:
                mapping[int(class_id)] = HELMET
        return mapping

    @property
    def class_names(self) -> list[str]:
        """Return the model's own class names (for diagnostics)."""
        return [str(name) for name in self.model.names.values()]

    def detect(self, image: np.ndarray) -> list[HeadDetection]:
        """Return helmet / no-helmet detections in an image."""
        if not isinstance(image, np.ndarray) or image.size == 0:
            return []

        results = self.model.predict(
            source=image,
            conf=self.settings.helmet_confidence,
            imgsz=self.settings.helmet_image_size,
            verbose=False,
        )

        detections: list[HeadDetection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                label = self.class_map.get(int(box.cls[0].item()))
                if label is None:
                    continue
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].cpu().tolist())
                detections.append(
                    HeadDetection(
                        label=label,
                        confidence=float(box.conf[0].item()),
                        bbox=(x1, y1, x2, y2),
                    )
                )
        return detections
