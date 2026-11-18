"""Coordinate the computer vision agents for each video frame."""

from dataclasses import dataclass

import numpy as np

from app.agents.helmet_agent import HelmetAgent, HelmetInput, HelmetOutput
from app.agents.plate_agent import PlateAgent, PlateInput, PlateOutput
from app.agents.speed_agent import SpeedAgent, SpeedInput, SpeedOutput
from app.agents.tracking_agent import (
    TrackedObject,
    TrackingAgent,
    TrackingInput,
    TrackingOutput,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FrameProcessingInput:
    """One frame and its position in the video."""

    frame: np.ndarray
    timestamp_seconds: float
    frame_index: int = 0


@dataclass(frozen=True)
class FrameProcessingOutput:
    """Combined result of all agents for one frame."""

    tracks: list[TrackedObject]
    speed_output: SpeedOutput
    plate_output: PlateOutput
    helmet_output: HelmetOutput | None = None


class FrameOrchestrator:
    """Coordinate vehicle tracking, speed measurement and plate OCR.

    The orchestrator decides which vehicles the PlateAgent should read:
    with ``OCR_MODE=overspeeding`` only violators - vehicles the SpeedAgent
    flagged and motorcycles the HelmetAgent found without a helmet.
    """

    def __init__(
        self,
        tracking_agent: TrackingAgent | None = None,
        speed_agent: SpeedAgent | None = None,
        plate_agent: PlateAgent | None = None,
        settings: Settings | None = None,
        helmet_agent: HelmetAgent | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.tracking_agent = tracking_agent or TrackingAgent(settings=self.settings)
        self.speed_agent = speed_agent or SpeedAgent(self.settings)
        self.plate_agent = plate_agent or PlateAgent(settings=self.settings)
        self.helmet_agent = helmet_agent or self._build_helmet_agent()
        self.read_all_plates = self.settings.ocr_mode == "all"
        self._violators: set[int] = set()

    @property
    def helmet_check_enabled(self) -> bool:
        """True when a helmet model is loaded."""
        return self.helmet_agent is not None

    def _build_helmet_agent(self) -> HelmetAgent | None:
        """Load the helmet model if it is enabled and present."""
        if not self.settings.helmet_detection_enabled:
            return None
        if not self.settings.resolved_helmet_model_path.is_file():
            logger.warning(
                "Helmet check disabled: no model at %s",
                self.settings.resolved_helmet_model_path,
            )
            return None
        from app.clients.helmet_detector_client import HelmetDetectorClient

        try:
            return HelmetAgent(HelmetDetectorClient(self.settings), self.settings)
        except (OSError, ValueError, ImportError) as exc:
            logger.error("Helmet check disabled: %s", exc)
            return None

    def reset(self) -> None:
        """Clear per-video state in the orchestrator and every agent."""
        self._violators.clear()
        agents = (
            self.tracking_agent,
            self.speed_agent,
            self.plate_agent,
            self.helmet_agent,
        )
        for agent in agents:
            reset = getattr(agent, "reset", None)
            if callable(reset):
                reset()

    def process_frame(
        self,
        data: FrameProcessingInput,
    ) -> FrameProcessingOutput:
        """Run tracking, speed and plate agents on one frame."""
        if not isinstance(data.frame, np.ndarray):
            raise TypeError("Frame must be a NumPy array.")

        if data.frame.size == 0:
            raise ValueError("Frame cannot be empty.")

        tracking_output: TrackingOutput = self.tracking_agent.run(
            TrackingInput(frame=data.frame)
        )

        speed_output = self.speed_agent.run(
            SpeedInput(
                tracks=tracking_output.tracks,
                timestamp_seconds=data.timestamp_seconds,
                frame_height=int(data.frame.shape[0]),
            )
        )

        for measurement in speed_output.measurements:
            if measurement.is_overspeeding:
                self._violators.add(measurement.track_id)

        helmet_output = None
        if self.helmet_agent is not None:
            helmet_output = self.helmet_agent.run(
                HelmetInput(
                    frame=data.frame,
                    tracks=tracking_output.tracks,
                    frame_index=data.frame_index,
                )
            )
            for status in helmet_output.newly_decided:
                if not status.has_helmet:
                    self._violators.add(status.track_id)

        plate_output = self.plate_agent.run(
            PlateInput(
                frame=data.frame,
                tracks=tracking_output.tracks,
                frame_index=data.frame_index,
                candidate_track_ids=(
                    None if self.read_all_plates else frozenset(self._violators)
                ),
            )
        )

        return FrameProcessingOutput(
            tracks=tracking_output.tracks,
            speed_output=speed_output,
            plate_output=plate_output,
            helmet_output=helmet_output,
        )
