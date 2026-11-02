from dataclasses import dataclass

import numpy as np

from app.agents.plate_agent import PlateAgent, PlateInput, PlateOutput
from app.agents.speed_agent import SpeedAgent, SpeedInput, SpeedOutput
from app.agents.tracking_agent import (
    TrackedObject,
    TrackingAgent,
    TrackingInput,
    TrackingOutput,
)


@dataclass(frozen=True)
class FrameProcessingInput:
    frame: np.ndarray
    timestamp_seconds: float
    frame_index: int = 0


@dataclass(frozen=True)
class FrameProcessingOutput:
    tracks: list[TrackedObject]
    speed_output: SpeedOutput
    plate_output: PlateOutput


class FrameOrchestrator:
    """Coordinate vehicle tracking, speed measurement, and plate OCR."""

    def __init__(
        self,
        tracking_agent: TrackingAgent | None = None,
        speed_agent: SpeedAgent | None = None,
        plate_agent: PlateAgent | None = None,
    ) -> None:
        self.tracking_agent = tracking_agent or TrackingAgent()
        self.speed_agent = speed_agent or SpeedAgent()
        self.plate_agent = plate_agent or PlateAgent()

    def process_frame(
        self,
        data: FrameProcessingInput,
    ) -> FrameProcessingOutput:
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
            )
        )

        plate_output = self.plate_agent.run(
            PlateInput(
                frame=data.frame,
                tracks=tracking_output.tracks,
                frame_index=data.frame_index,
            )
        )

        return FrameProcessingOutput(
            tracks=tracking_output.tracks,
            speed_output=speed_output,
            plate_output=plate_output,
        )




