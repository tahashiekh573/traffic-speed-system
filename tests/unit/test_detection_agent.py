
import numpy as np

from app.agents.detection_agent import DetectionAgent, DetectionInput
from app.clients.detector_client import Detection


class FakeDetector:
    def detect(self, frame):
        return [
            Detection(
                bbox=(0, 0, 100, 100),
                confidence=0.9,
                class_id=2,
                class_name="car",
            ),
            Detection(
                bbox=(10, 10, 50, 50),
                confidence=0.8,
                class_id=0,
                class_name="person",
            ),
            Detection(
                bbox=(20, 20, 80, 80),
                confidence=0.95,
                class_id=5,
                class_name="bus",
            ),
        ]


def test_detection_agent_filters_only_vehicles():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)

    agent = DetectionAgent(detector=FakeDetector())

    output = agent.run(DetectionInput(frame=frame))

    assert len(output.detections) == 2

    names = {d.class_name for d in output.detections}

    assert names == {"car", "bus"}
