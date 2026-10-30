import numpy as np

from app.agents.plate_agent import PlateAgent, PlateInput
from app.agents.tracking_agent import TrackedObject


class FakeOCRClient:
    def __init__(self, results=None):
        self.results = results or []

    def read_text(self, image):
        return self.results


def make_track(
    track_id=1,
    bbox=(10.0, 10.0, 90.0, 90.0),
):
    return TrackedObject(
        track_id=track_id,
        bbox=bbox,
        confidence=0.95,
        class_id=2,
        class_name="car",
    )


def test_plate_agent_reads_and_normalizes_plate():
    agent = PlateAgent(
        ocr_client=FakeOCRClient(["abc-1234"])
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = agent.run(
        PlateInput(frame=frame, tracks=[make_track()])
    )

    assert len(result.readings) == 1
    assert result.readings[0].track_id == 1
    assert result.readings[0].plate_text == "ABC1234"


def test_plate_agent_ignores_invalid_ocr_text():
    agent = PlateAgent(
        ocr_client=FakeOCRClient(["!!!", "AB"])
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = agent.run(
        PlateInput(frame=frame, tracks=[make_track()])
    )

    assert result.readings == []


def test_plate_agent_skips_invalid_bounding_box():
    agent = PlateAgent(ocr_client=FakeOCRClient(["ABC1234"]))
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = agent.run(
        PlateInput(
            frame=frame,
            tracks=[make_track(bbox=(50.0, 50.0, 20.0, 20.0))],
        )
    )

    assert result.readings == []


def test_plate_agent_rejects_empty_frame():
    agent = PlateAgent(ocr_client=FakeOCRClient([]))

    try:
        agent.run(
            PlateInput(
                frame=np.array([]),
                tracks=[],
            )
        )
    except ValueError as error:
        assert str(error) == "Frame cannot be empty."
    else:
        raise AssertionError("Expected ValueError for empty frame.")
