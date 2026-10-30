from types import SimpleNamespace

import numpy as np

from app.agents.tracking_agent import TrackingAgent, TrackingInput


class FakeModel:
    def track(self, **kwargs):
        assert kwargs["persist"] is True
        assert kwargs["tracker"] == "bytetrack.yaml"

        boxes = SimpleNamespace(
            xyxy=np.array([[10, 20, 100, 150]]),
            conf=np.array([0.95]),
            cls=np.array([2]),
            id=np.array([7]),
        )

        result = SimpleNamespace(
            boxes=boxes,
            names={2: "car"},
        )

        return [result]


class FakeDetector:
    def __init__(self):
        self.model = FakeModel()


def test_tracking_agent_returns_tracked_objects():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)

    agent = TrackingAgent(detector=FakeDetector())

    output = agent.run(TrackingInput(frame=frame))

    assert len(output.tracks) == 1

    vehicle = output.tracks[0]

    assert vehicle.track_id == 7
    assert vehicle.class_name == "car"
    assert vehicle.confidence == 0.95
    assert vehicle.bbox == (10.0, 20.0, 100.0, 150.0)


def test_tracking_agent_returns_empty_when_no_track_ids():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)

    class NoTrackModel:
        def track(self, **kwargs):
            boxes = SimpleNamespace(id=None)

            return [
                SimpleNamespace(
                    boxes=boxes,
                    names={},
                )
            ]

    class NoTrackDetector:
        model = NoTrackModel()

    agent = TrackingAgent(detector=NoTrackDetector())

    output = agent.run(TrackingInput(frame=frame))

    assert output.tracks == []
