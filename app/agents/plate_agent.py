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
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PlateInput:
    """Frame, tracked vehicles and which of them are worth reading.

    ``candidate_track_ids`` limits OCR to those tracks (for example only
    overspeeding vehicles). ``None`` means every tracked vehicle.
    """

    frame: np.ndarray
    tracks: list[TrackedObject]
    frame_index: int = 0
    candidate_track_ids: frozenset[int] | None = None
    # Read these first (e.g. violators); they may also be off-screen.
    priority_track_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class PlateReading:
    """A plate accepted for one tracked vehicle."""

    track_id: int
    plate_text: str


@dataclass(frozen=True)
class PlateOutput:
    """All plates known for the vehicles in the current frame."""

    readings: list[PlateReading]
    # Vehicles whose plate was attempted (OCR run) in this frame.
    attempted_track_ids: tuple[int, ...] = ()


class PlateAgent(BaseAgent[PlateInput, PlateOutput]):
    """Read vehicle number plates with a bounded OCR budget per frame.

    OCR is by far the slowest step on CPU, so each frame reads at most
    ``OCR_MAX_PER_FRAME`` vehicles (largest boxes first), each vehicle is
    retried at most ``OCR_MAX_ATTEMPTS_PER_TRACK`` times, at least
    ``OCR_FRAME_INTERVAL`` frames apart, and accepted plates are cached.
    """

    def __init__(
        self,
        ocr_client: OCRClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        self.ocr_client = (
            ocr_client
            if ocr_client is not None
            else EasyOCRClient(
                languages=self.settings.ocr_language_list,
                min_confidence=self.settings.ocr_min_confidence,
                use_gpu=self.settings.ocr_use_gpu,
                max_image_width=self.settings.ocr_max_crop_width,
            )
        )

        self.ocr_frame_interval = max(1, int(self.settings.ocr_frame_interval))
        self.max_per_frame = int(self.settings.ocr_max_per_frame)
        self.max_attempts = int(self.settings.ocr_max_attempts_per_track)
        self.min_box_height = int(self.settings.ocr_min_box_height)

        # Accept a valid plate after one OCR observation.
        self.minimum_votes = 1

        self._plate_cache: dict[int, str] = {}
        self._candidate_votes: dict[int, Counter] = {}
        self._attempts: dict[int, int] = {}
        self._last_attempt_frame: dict[int, int] = {}
        self._last_frame_index: int | None = None
        # Best (largest) plate crop seen for every vehicle, so a plate can
        # still be read after the vehicle is flagged - even off-screen.
        self._best_crops: dict[int, tuple[float, np.ndarray, int]] = {}

    def reset(self) -> None:
        """Forget all per-video state before a new video starts."""
        self._plate_cache.clear()
        self._candidate_votes.clear()
        self._attempts.clear()
        self._last_attempt_frame.clear()
        self._best_crops.clear()
        self._last_frame_index = None

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

    BEST_CROP_MAX_WIDTH = 480
    BEST_CROP_TTL_FRAMES = 300

    def _remember_crop(
        self, frame: np.ndarray, track: TrackedObject, index: int
    ) -> None:
        """Keep the largest plate crop seen so far for this vehicle."""
        height = track.bbox[3] - track.bbox[1]
        stored = self._best_crops.get(track.track_id)

        if stored is not None and stored[0] >= height:
            self._best_crops[track.track_id] = (stored[0], stored[1], index)
            return

        crop = self._crop_plate_region(frame, track.bbox)
        if crop is None:
            return

        if crop.shape[1] > self.BEST_CROP_MAX_WIDTH:
            factor = self.BEST_CROP_MAX_WIDTH / crop.shape[1]
            crop = cv2.resize(
                crop, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA
            )
        else:
            crop = crop.copy()

        self._best_crops[track.track_id] = (height, crop, index)

    def _forget_stale_crops(self, frame_index: int, keep: frozenset[int]) -> None:
        """Drop crops of vehicles that left long ago and are not needed."""
        stale = [
            track_id
            for track_id, (_, _, seen) in self._best_crops.items()
            if frame_index - seen > self.BEST_CROP_TTL_FRAMES and track_id not in keep
        ]
        for track_id in stale:
            del self._best_crops[track_id]

    def _is_due(self, track_id: int, box_height: float, frame_index: int) -> bool:
        """Return True when this vehicle should be OCR'd now."""
        if track_id in self._plate_cache:
            return False

        if self._attempts.get(track_id, 0) >= self.max_attempts:
            return False

        last = self._last_attempt_frame.get(track_id)
        if last is not None and frame_index - last < self.ocr_frame_interval:
            return False

        return box_height >= self.min_box_height

    def _read_plate(self, track_id: int, crop: np.ndarray) -> str | None:
        """Run OCR on a stored crop and return the best plate so far."""
        enhanced = self._enhance_crop(crop)

        if enhanced is None:
            return None

        try:
            candidates = self.ocr_client.read_text(enhanced)
        except Exception as exc:  # OCR failures must not stop the video.
            logger.warning("OCR failed for track %s: %s", track_id, exc)
            return None

        valid = {
            plate
            for candidate in candidates
            if (plate := self._normalize_plate(candidate)) is not None
        }

        if not valid:
            return None

        votes = self._candidate_votes.setdefault(track_id, Counter())
        for plate in valid:
            votes[plate] += 1

        best_plate, best_votes = max(
            votes.items(),
            key=lambda item: (item[1], len(item[0])),
        )

        return best_plate if best_votes >= self.minimum_votes else None

    def run(self, data: PlateInput) -> PlateOutput:
        """Return known plates and OCR a few due vehicles (largest first)."""
        if not isinstance(data.frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        if (
            self._last_frame_index is not None
            and data.frame_index <= self._last_frame_index
        ):
            self.reset()

        self._last_frame_index = data.frame_index
        candidates = data.candidate_track_ids
        priority = data.priority_track_ids

        for track in data.tracks:
            if track.track_id not in self._plate_cache:
                self._remember_crop(data.frame, track, data.frame_index)

        # Vehicles that may be read now: visible ones, plus flagged vehicles
        # that already left the frame but whose best crop is stored.
        pool = {track.track_id for track in data.tracks}
        if candidates is not None:
            pool = (pool & candidates) | (candidates & self._best_crops.keys())
        pool |= priority & self._best_crops.keys()

        due = [
            (track_id, self._best_crops[track_id])
            for track_id in pool
            if track_id in self._best_crops
            and self._is_due(track_id, self._best_crops[track_id][0], data.frame_index)
        ]
        # Violators first, then the largest (closest, most readable) plates.
        due.sort(key=lambda item: (item[0] in priority, item[1][0]), reverse=True)

        newly_read: list[PlateReading] = []
        attempted: list[int] = []
        for track_id, (_, crop, _) in due[: self.max_per_frame]:
            attempted.append(track_id)
            self._attempts[track_id] = self._attempts.get(track_id, 0) + 1
            self._last_attempt_frame[track_id] = data.frame_index

            plate = self._read_plate(track_id, crop)
            if plate is not None:
                self._plate_cache[track_id] = plate
                self._best_crops.pop(track_id, None)
                newly_read.append(PlateReading(track_id, plate))

        keep = (candidates or frozenset()) | priority
        self._forget_stale_crops(data.frame_index, keep)

        visible = {track.track_id for track in data.tracks}
        readings = [
            PlateReading(track_id, plate)
            for track_id, plate in self._plate_cache.items()
            if track_id in visible
        ]
        readings += [r for r in newly_read if r.track_id not in visible]
        return PlateOutput(readings=readings, attempted_track_ids=tuple(attempted))
