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


class CountingOCRClient:
    def __init__(self, text="ABC1234"):
        self.calls = 0
        self.text = text

    def read_text(self, image):
        self.calls += 1
        return [self.text]


def test_plate_agent_only_reads_candidate_tracks():
    ocr = CountingOCRClient()
    agent = PlateAgent(ocr_client=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = agent.run(
        PlateInput(
            frame=frame,
            tracks=[make_track(1), make_track(2)],
            candidate_track_ids=frozenset({2}),
        )
    )

    assert [r.track_id for r in result.readings] == [2]
    assert ocr.calls == 1


def test_plate_agent_limits_ocr_per_frame_and_caches_plates():
    from app.core.config import Settings

    ocr = CountingOCRClient()
    agent = PlateAgent(ocr_client=ocr, settings=Settings(ocr_max_per_frame=1))
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    tracks = [make_track(1), make_track(2)]

    first = agent.run(PlateInput(frame=frame, tracks=tracks, frame_index=0))
    second = agent.run(PlateInput(frame=frame, tracks=tracks, frame_index=1))
    third = agent.run(PlateInput(frame=frame, tracks=tracks, frame_index=2))

    assert len(first.readings) == 1
    assert len(second.readings) == 2  # cached plate + one new read
    assert len(third.readings) == 2   # both cached, no new OCR
    assert ocr.calls == 2


def test_plate_agent_skips_small_vehicles():
    from app.core.config import Settings

    ocr = CountingOCRClient()
    agent = PlateAgent(ocr_client=ocr, settings=Settings(ocr_min_box_height=200))
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = agent.run(PlateInput(frame=frame, tracks=[make_track()]))

    assert result.readings == []
    assert ocr.calls == 0


def test_plate_agent_reads_flagged_vehicle_after_it_left_the_frame():
    ocr = CountingOCRClient("LEA1234")
    agent = PlateAgent(ocr_client=ocr)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Vehicle is visible but not (yet) a violator: its crop is only stored.
    agent.run(
        PlateInput(
            frame=frame,
            tracks=[make_track(9)],
            frame_index=0,
            candidate_track_ids=frozenset(),
        )
    )
    assert ocr.calls == 0

    # It is flagged after leaving the frame; the stored crop is read.
    result = agent.run(
        PlateInput(
            frame=frame,
            tracks=[],
            frame_index=1,
            candidate_track_ids=frozenset({9}),
        )
    )

    assert ocr.calls == 1
    assert [(r.track_id, r.plate_text) for r in result.readings] == [(9, "LEA1234")]


def test_plate_agent_reads_violators_before_larger_vehicles():
    from app.core.config import Settings

    ocr = CountingOCRClient()
    agent = PlateAgent(ocr_client=ocr, settings=Settings(ocr_max_per_frame=1))
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    big = make_track(1, bbox=(10.0, 10.0, 190.0, 190.0))
    small_violator = make_track(2, bbox=(10.0, 10.0, 90.0, 90.0))

    result = agent.run(
        PlateInput(
            frame=frame,
            tracks=[big, small_violator],
            priority_track_ids=frozenset({2}),
        )
    )

    assert result.attempted_track_ids == (2,)
    assert [r.track_id for r in result.readings] == [2]
