
import numpy as np
from ultralytics import YOLO

from app.clients.detector_client import Detection
from app.core.config import Settings, get_settings


class YOLODetectorClient:
    """YOLOv8 implementation of the detector client interface."""

    def __init__(
        self,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        self.model_path = self.settings.resolved_yolo_model_path
        self.confidence_threshold = self.settings.confidence_threshold

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"YOLO model not found: {self.model_path}. "
                "Download yolov8n.pt into the weights directory."
            )

        self.model = YOLO(str(self.model_path))

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect objects in a frame and return structured results."""

        if not isinstance(frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        results = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            verbose=False,
        )

        detections: list[Detection] = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                coordinates = box.xyxy[0].cpu().tolist()

                bbox = (
                    float(coordinates[0]),
                    float(coordinates[1]),
                    float(coordinates[2]),
                    float(coordinates[3]),
                )

                confidence = float(box.conf[0].cpu().item())
                class_id = int(box.cls[0].cpu().item())

                class_name = result.names[class_id]

                detections.append(
                    Detection(
                        bbox=bbox,
                        confidence=confidence,
                        class_id=class_id,
                        class_name=str(class_name),
                    )
                )

        return detections

