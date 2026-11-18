import numpy as np

from app.agents.helmet_agent import HelmetAgent, HelmetInput
from app.agents.tracking_agent import TrackedObject
from app.clients.helmet_detector_client import HELMET, NO_HELMET, HeadDetection
from app.core.config import Settings

SETTINGS = Settings(
    helmet_votes_required=2,
    helmet_frame_interval=1,
    helmet_min_box_height=10,
)


class FakeHeadDetector:
    def __init__(self, labels):
        self.labels = labels
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        return [HeadDetection(label, 0.8, (0, 0, 5, 5)) for label in self.labels]


def make_track(track_id=1, class_name="motorcycle", bbox=(40, 60, 80, 100)):
    return TrackedObject(track_id, bbox, 0.9, 3, class_name)


def run(agent, tracks, index):
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    return agent.run(HelmetInput(frame=frame, tracks=tracks, frame_index=index))


def test_rider_without_helmet_is_flagged_after_enough_votes():
    agent = HelmetAgent(FakeHeadDetector([NO_HELMET]), SETTINGS)

    first = run(agent, [make_track()], 0)
    second = run(agent, [make_track()], 1)

    assert first.statuses == []
    assert [(s.track_id, s.has_helmet) for s in second.newly_decided] == [(1, False)]
    assert second.statuses[0].has_helmet is False


def test_rider_with_helmet_is_ok_and_checked_only_until_decided():
    detector = FakeHeadDetector([HELMET])
    agent = HelmetAgent(detector, SETTINGS)

    for index in range(5):
        output = run(agent, [make_track()], index)

    assert output.statuses[0].has_helmet is True
    assert detector.calls == 2


def test_cars_are_not_checked():
    detector = FakeHeadDetector([NO_HELMET])
    agent = HelmetAgent(detector, SETTINGS)

    output = run(agent, [make_track(class_name="car")], 0)

    assert output.statuses == []
    assert detector.calls == 0


def test_rider_region_covers_area_above_the_motorcycle():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)

    crop = HelmetAgent.rider_region(frame, (50, 100, 100, 150))

    # 1.1 x height above the box top and 0.6 x height into the box.
    assert abs(crop.shape[0] - ((100 + 30) - (100 - 55))) <= 1
