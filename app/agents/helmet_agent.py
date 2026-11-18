"""Check whether motorcycle riders wear a helmet."""

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.agents.base_agent import BaseAgent
from app.agents.tracking_agent import TrackedObject
from app.clients.helmet_detector_client import NO_HELMET, HeadDetection
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class HeadDetector(Protocol):
    """Anything that finds helmet / no-helmet heads in an image."""

    def detect(self, image: np.ndarray) -> list[HeadDetection]: ...


@dataclass(frozen=True)
class HelmetInput:
    """A frame and its tracked vehicles."""

    frame: np.ndarray
    tracks: list[TrackedObject]
    frame_index: int = 0


@dataclass(frozen=True)
class HelmetStatus:
    """Final helmet decision for one motorcycle."""

    track_id: int
    has_helmet: bool
    confidence: float


@dataclass(frozen=True)
class HelmetOutput:
    """Helmet decisions for the motorcycles visible in this frame."""

    statuses: list[HelmetStatus]
    # Decided in this very frame (useful for saving each violation once).
    newly_decided: list[HelmetStatus]


class HelmetAgent(BaseAgent[HelmetInput, HelmetOutput]):
    """Decide per motorcycle whether its rider(s) wear a helmet.

    The region around and above the motorcycle box (where the riders'
    heads are) is checked every few frames. A decision is made after
    ``HELMET_VOTES_REQUIRED`` observations; any confident "no helmet" head
    in the majority of observations marks the motorcycle as a violation.
    """

    def __init__(
        self,
        detector: HeadDetector,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detector = detector
        self.rider_classes = self.settings.helmet_rider_class_names
        self.votes_required = self.settings.helmet_votes_required
        self.interval = self.settings.helmet_frame_interval
        self.max_per_frame = self.settings.helmet_max_per_frame
        self.min_box_height = self.settings.helmet_min_box_height

        self._votes: dict[int, Counter] = {}
        self._confidence: dict[int, float] = {}
        self._last_check: dict[int, int] = {}
        self._decided: dict[int, HelmetStatus] = {}
        self._last_frame_index: int | None = None

    def reset(self) -> None:
        """Forget all per-video state before a new video starts."""
        self._votes.clear()
        self._confidence.clear()
        self._last_check.clear()
        self._decided.clear()
        self._last_frame_index = None

    @staticmethod
    def rider_region(
        frame: np.ndarray,
        bbox: tuple[float, float, float, float],
    ) -> np.ndarray | None:
        """Crop the area where the riders' heads are: above and on the bike."""
        frame_h, frame_w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        width, height = x2 - x1, y2 - y1
        if width <= 0 or height <= 0:
            return None

        left = int(max(0, x1 - 0.15 * width))
        right = int(min(frame_w, x2 + 0.15 * width))
        top = int(max(0, y1 - 1.1 * height))
        bottom = int(min(frame_h, y1 + 0.6 * height))

        crop = frame[top:bottom, left:right]
        return crop if crop.size else None

    def _check_due(self, track_id: int, frame_index: int) -> bool:
        last = self._last_check.get(track_id)
        return last is None or frame_index - last >= self.interval

    def _observe(self, track_id: int, heads: list[HeadDetection]) -> None:
        if not heads:
            return
        votes = self._votes.setdefault(track_id, Counter())
        no_helmet = [h for h in heads if h.label == NO_HELMET]
        if no_helmet:
            votes["no_helmet"] += 1
            best = max(h.confidence for h in no_helmet)
        else:
            votes["helmet"] += 1
            best = max(h.confidence for h in heads)
        self._confidence[track_id] = max(self._confidence.get(track_id, 0.0), best)

    def _decide(self, track_id: int) -> HelmetStatus | None:
        votes = self._votes.get(track_id)
        if not votes or sum(votes.values()) < self.votes_required:
            return None
        return HelmetStatus(
            track_id=track_id,
            has_helmet=votes["no_helmet"] <= votes["helmet"],
            confidence=round(self._confidence.get(track_id, 0.0), 3),
        )

    def run(self, data: HelmetInput) -> HelmetOutput:
        """Check a few undecided motorcycles and return all decisions."""
        if not isinstance(data.frame, np.ndarray) or data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        last = self._last_frame_index
        if last is not None and data.frame_index <= last:
            self.reset()
        self._last_frame_index = data.frame_index

        riders = [
            t for t in data.tracks
            if t.class_name.lower() in self.rider_classes
            and t.track_id not in self._decided
            and (t.bbox[3] - t.bbox[1]) >= self.min_box_height
            and self._check_due(t.track_id, data.frame_index)
        ]
        riders.sort(key=lambda t: t.bbox[3] - t.bbox[1], reverse=True)

        newly: list[HelmetStatus] = []
        for track in riders[: self.max_per_frame]:
            self._last_check[track.track_id] = data.frame_index
            region = self.rider_region(data.frame, track.bbox)
            if region is None:
                continue
            try:
                heads = self.detector.detect(region)
            except Exception as exc:  # A failed check must not stop the video.
                logger.warning(
                    "Helmet check failed for track %s: %s", track.track_id, exc
                )
                continue
            self._observe(track.track_id, heads)
            status = self._decide(track.track_id)
            if status is not None:
                self._decided[track.track_id] = status
                newly.append(status)

        visible = {t.track_id for t in data.tracks}
        statuses = [s for tid, s in self._decided.items() if tid in visible]
        return HelmetOutput(statuses=statuses, newly_decided=newly)
