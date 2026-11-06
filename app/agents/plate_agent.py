
import re
from collections import Counter
from dataclasses import dataclass

import cv2
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
    """Lightweight vehicle number plate OCR agent."""

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

        # Run OCR at most once every configured interval.
        self.ocr_frame_interval = max(
            1,
            int(self.settings.ocr_frame_interval),
        )

        # Accept a valid plate after one OCR observation.
        self.minimum_votes = 1

        self._plate_cache: dict[int, str] = {}
        self._candidate_votes: dict[int, Counter] = {}
        self._last_frame_index: int | None = None

    @staticmethod
    def _crop_plate_region(
        frame: np.ndarray,
        bbox: tuple[float, float, float, float],
    ) -> np.ndarray | None:

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

        margin_x = int(width * 0.03)

        crop_x1 = x1 + margin_x
        crop_x2 = x2 - margin_x
        crop_y1 = y1 + int(height * 0.50)

        crop = frame[crop_y1:y2, crop_x1:crop_x2]

        if crop.size == 0:
            return None

        return crop

    @staticmethod
    def _enhance_crop(crop: np.ndarray) -> np.ndarray | None:
        """Create one enhanced image for faster OCR."""

        if crop is None or crop.size == 0:
            return None

        height, width = crop.shape[:2]

        if height < 2 or width < 2:
            return None

        enlarged = cv2.resize(
            crop,
            None,
            fx=2,
            fy=2,
            interpolation=cv2.INTER_CUBIC,
        )

        if len(enlarged.shape) == 3:
            gray = cv2.cvtColor(
                enlarged,
                cv2.COLOR_BGR2GRAY,
            )
        else:
            gray = enlarged.copy()

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        )

        return clahe.apply(gray)

    @staticmethod
    def _normalize_plate(text: str) -> str | None:

        normalized = re.sub(
            r"[^A-Z0-9]",
            "",
            text.upper(),
        )

        if not re.fullmatch(r"[A-Z0-9]{4,12}", normalized):
            return None

        if not any(char.isalpha() for char in normalized):
            return None

        if not any(char.isdigit() for char in normalized):
            return None

        return normalized

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
            self._candidate_votes.clear()

        self._last_frame_index = data.frame_index

        active_track_ids = {
            track.track_id for track in data.tracks
        }

        self._plate_cache = {
            track_id: plate
            for track_id, plate in self._plate_cache.items()
            if track_id in active_track_ids
        }

        self._candidate_votes = {
            track_id: votes
            for track_id, votes in self._candidate_votes.items()
            if track_id in active_track_ids
        }

        should_run_ocr = (
            data.frame_index % self.ocr_frame_interval == 0
        )

        readings = []

        for track in data.tracks:

            track_id = track.track_id

            cached_plate = self._plate_cache.get(track_id)

            if cached_plate is not None:
                readings.append(
                    PlateReading(
                        track_id=track_id,
                        plate_text=cached_plate,
                    )
                )
                continue

            if not should_run_ocr:
                continue

            crop = self._crop_plate_region(
                data.frame,
                track.bbox,
            )

            if crop is None:
                continue

            enhanced = self._enhance_crop(crop)

            if enhanced is None:
                continue

            try:
                candidates = self.ocr_client.read_text(enhanced)
            except Exception:
                continue

            valid_candidates = {
                plate
                for candidate in candidates
                if (
                    plate := self._normalize_plate(candidate)
                ) is not None
            }

            if not valid_candidates:
                continue

            votes = self._candidate_votes.setdefault(
                track_id,
                Counter(),
            )

            for plate in valid_candidates:
                votes[plate] += 1

            best_plate, best_votes = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    len(item[0]),
                ),
            )

            if best_votes >= self.minimum_votes:
                self._plate_cache[track_id] = best_plate

                readings.append(
                    PlateReading(
                        track_id=track_id,
                        plate_text=best_plate,
                    )
                )

        return PlateOutput(readings=readings)
