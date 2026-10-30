import re
from dataclasses import dataclass

import numpy as np

from app.agents.base_agent import BaseAgent
from app.agents.tracking_agent import TrackedObject
from app.clients.easyocr_client import EasyOCRClient
from app.clients.ocr_client import OCRClient
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class PlateInput:
    frame: np.ndarray
    tracks: list[TrackedObject]


@dataclass(frozen=True)
class PlateReading:
    track_id: int
    plate_text: str


@dataclass(frozen=True)
class PlateOutput:
    readings: list[PlateReading]


class PlateAgent(BaseAgent[PlateInput, PlateOutput]):
    """Read vehicle number plates using an OCR client."""

    def __init__(
        self,
        ocr_client: OCRClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        languages = [
            language.strip()
            for language in self.settings.ocr_languages.split(",")
            if language.strip()
        ]

        self.ocr_client = (
            ocr_client
            if ocr_client is not None
            else EasyOCRClient(languages=languages)
        )

    @staticmethod
    def _crop_plate_region(
        frame: np.ndarray,
        bbox: tuple[float, float, float, float],
    ) -> np.ndarray | None:
        """Crop the lower portion of a vehicle bounding box."""

        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = bbox

        x1 = max(0, min(int(x1), frame_width))
        x2 = max(0, min(int(x2), frame_width))
        y1 = max(0, min(int(y1), frame_height))
        y2 = max(0, min(int(y2), frame_height))

        width = x2 - x1
        height = y2 - y1

        if width <= 0 or height <= 0:
            return None

        margin_x = int(width * 0.05)
        crop_x1 = x1 + margin_x
        crop_x2 = x2 - margin_x
        crop_y1 = y1 + int(height * 0.45)

        crop = frame[crop_y1:y2, crop_x1:crop_x2]

        if crop.size == 0:
            return None

        return crop

    @staticmethod
    def _normalize_plate(text: str) -> str | None:
        """Normalize and validate an OCR text candidate."""

        normalized = re.sub(r"[^A-Z0-9]", "", text.upper())

        if re.fullmatch(r"[A-Z0-9]{4,12}", normalized):
            return normalized

        return None

    def run(self, data: PlateInput) -> PlateOutput:
        if not isinstance(data.frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        readings = []

        for track in data.tracks:
            crop = self._crop_plate_region(data.frame, track.bbox)

            if crop is None:
                continue

            candidates = self.ocr_client.read_text(crop)

            valid_candidates = [
                plate
                for candidate in candidates
                if (plate := self._normalize_plate(candidate)) is not None
            ]

            if not valid_candidates:
                continue

            plate_text = max(valid_candidates, key=len)

            readings.append(
                PlateReading(
                    track_id=track.track_id,
                    plate_text=plate_text,
                )
            )

        return PlateOutput(readings=readings)
