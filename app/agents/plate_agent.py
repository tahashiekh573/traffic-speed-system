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
    frame_index: int = 0


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

        self.ocr_frame_interval = self.settings.ocr_frame_interval
        self._plate_cache: dict[int, str] = {}
        self._last_frame_index: int | None = None

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

        if (
            self._last_frame_index is not None
            and data.frame_index <= self._last_frame_index
        ):
            self._plate_cache.clear()

        self._last_frame_index = data.frame_index

        active_track_ids = {track.track_id for track in data.tracks}

        self._plate_cache = {
            track_id: plate_text
            for track_id, plate_text in self._plate_cache.items()
            if track_id in active_track_ids
        }

        should_run_ocr = (
            data.frame_index % self.ocr_frame_interval == 0
        )

        readings = []

        for track in data.tracks:
            cached_plate = self._plate_cache.get(track.track_id)

            if cached_plate is not None:
                readings.append(
                    PlateReading(
                        track_id=track.track_id,
                        plate_text=cached_plate,
                    )
                )
                continue

            if not should_run_ocr:
                continue

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
            self._plate_cache[track.track_id] = plate_text

            readings.append(
                PlateReading(
                    track_id=track.track_id,
                    plate_text=plate_text,
                )
            )

        return PlateOutput(readings=readings)
