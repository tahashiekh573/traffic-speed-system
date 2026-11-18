import numpy as np
import pytest

from app.agents.plate_agent import PlateOutput
from app.agents.speed_agent import SpeedOutput
from app.agents.tracking_agent import TrackedObject, TrackingOutput
from app.orchestrators.frame_orchestrator import (
    FrameOrchestrator,
    FrameProcessingInput,
)


class FakeTrackingAgent:
    def __init__(self):
        self.received_frame = None
        self.tracks = [
            TrackedObject(
                track_id=1,
                bbox=(10.0, 20.0, 100.0, 120.0),
                confidence=0.95,
                class_id=2,
                class_name="car",
            )
        ]

    def run(self, data):
        self.received_frame = data.frame
        return TrackingOutput(tracks=self.tracks)


class FakeSpeedAgent:
    def __init__(self):
        self.received_input = None
        self.output = SpeedOutput(measurements=[])

    def run(self, data):
        self.received_input = data
        return self.output


class FakePlateAgent:
    def __init__(self):
        self.received_input = None
        self.output = PlateOutput(readings=[])

    def run(self, data):
        self.received_input = data
        return self.output


def test_orchestrator_processes_frame_and_combines_outputs():
    tracking_agent = FakeTrackingAgent()
    speed_agent = FakeSpeedAgent()
    plate_agent = FakePlateAgent()

    orchestrator = FrameOrchestrator(
        tracking_agent=tracking_agent,
        speed_agent=speed_agent,
        plate_agent=plate_agent,
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    timestamp = 1.5

    result = orchestrator.process_frame(
        FrameProcessingInput(
            frame=frame,
            timestamp_seconds=timestamp,
        )
    )

    assert result.tracks == tracking_agent.tracks
    assert result.speed_output is speed_agent.output
    assert result.plate_output is plate_agent.output

    assert tracking_agent.received_frame is frame
    assert speed_agent.received_input.tracks == tracking_agent.tracks
    assert speed_agent.received_input.timestamp_seconds == timestamp
    assert plate_agent.received_input.frame is frame
    assert plate_agent.received_input.tracks == tracking_agent.tracks


def test_orchestrator_rejects_non_numpy_frame():
    orchestrator = FrameOrchestrator(
        tracking_agent=FakeTrackingAgent(),
        speed_agent=FakeSpeedAgent(),
        plate_agent=FakePlateAgent(),
    )

    with pytest.raises(TypeError, match="Frame must be a NumPy array"):
        orchestrator.process_frame(
            FrameProcessingInput(
                frame="invalid",
                timestamp_seconds=1.0,
            )
        )


def test_orchestrator_rejects_empty_frame():
    orchestrator = FrameOrchestrator(
        tracking_agent=FakeTrackingAgent(),
        speed_agent=FakeSpeedAgent(),
        plate_agent=FakePlateAgent(),
    )

    with pytest.raises(ValueError, match="Frame cannot be empty"):
        orchestrator.process_frame(
            FrameProcessingInput(
                frame=np.array([], dtype=np.uint8),
                timestamp_seconds=1.0,
            )
        )


def test_orchestrator_reads_plates_of_overspeeding_vehicles_only():
    from app.agents.speed_agent import SpeedMeasurement
    from app.core.config import Settings

    tracking_agent = FakeTrackingAgent()
    speed_agent = FakeSpeedAgent()
    plate_agent = FakePlateAgent()

    orchestrator = FrameOrchestrator(
        tracking_agent=tracking_agent,
        speed_agent=speed_agent,
        plate_agent=plate_agent,
        settings=Settings(ocr_mode="overspeeding"),
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    orchestrator.process_frame(FrameProcessingInput(frame=frame, timestamp_seconds=0.0))
    assert plate_agent.received_input.candidate_track_ids == frozenset()

    speed_agent.output = SpeedOutput(
        measurements=[
            SpeedMeasurement(track_id=1, speed_kmh=90.0, is_overspeeding=True)
        ]
    )
    orchestrator.process_frame(
        FrameProcessingInput(frame=frame, timestamp_seconds=0.1, frame_index=1)
    )
    assert plate_agent.received_input.candidate_track_ids == frozenset({1})

    orchestrator.reset()
    speed_agent.output = SpeedOutput(measurements=[])
    orchestrator.process_frame(
        FrameProcessingInput(frame=frame, timestamp_seconds=0.2, frame_index=2)
    )
    assert plate_agent.received_input.candidate_track_ids == frozenset()


def test_orchestrator_reads_all_plates_in_all_mode():
    from app.core.config import Settings

    plate_agent = FakePlateAgent()
    orchestrator = FrameOrchestrator(
        tracking_agent=FakeTrackingAgent(),
        speed_agent=FakeSpeedAgent(),
        plate_agent=plate_agent,
        settings=Settings(ocr_mode="all"),
    )

    orchestrator.process_frame(
        FrameProcessingInput(
            frame=np.zeros((480, 640, 3), dtype=np.uint8),
            timestamp_seconds=0.0,
        )
    )

    assert plate_agent.received_input.candidate_track_ids is None
