import numpy as np
import pytest

from app.services.video_processing_service import VideoProcessingService


class FakeVideoClient:
    def __init__(self, video_path):
        self.video_path = video_path
        self.frames = [
            np.zeros((480, 640, 3), dtype=np.uint8)
            for _ in range(3)
        ]
        self.current_index = 0
        self.released = False
        self.fps = 30.0
        self.width = 640
        self.height = 480
        self.frame_count = 3

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def read(self):
        if self.current_index >= len(self.frames):
            return False, None

        frame = self.frames[self.current_index]
        self.current_index += 1
        return True, frame

    @property
    def timestamp_seconds(self):
        return (self.current_index - 1) / self.fps

    def release(self):
        self.released = True


class FakeOrchestrator:
    def __init__(self):
        self.received_inputs = []

    def process_frame(self, data):
        self.received_inputs.append(data)
        return {"frame_index": len(self.received_inputs)}


def test_process_video_processes_all_frames():
    video_client = FakeVideoClient("sample.mp4")
    orchestrator = FakeOrchestrator()

    service = VideoProcessingService(
        orchestrator=orchestrator,
        video_client_factory=lambda path: video_client,
    )

    results = []

    result = service.process_video(
        "sample.mp4",
        on_frame_processed=results.append,
    )

    assert result.processed_frames == 3
    assert result.total_frames == 3
    assert result.fps == 30.0
    assert result.width == 640
    assert result.height == 480

    assert len(orchestrator.received_inputs) == 3
    assert len(results) == 3
    assert video_client.released is True


def test_process_video_passes_correct_timestamps():
    video_client = FakeVideoClient("sample.mp4")
    orchestrator = FakeOrchestrator()

    service = VideoProcessingService(
        orchestrator=orchestrator,
        video_client_factory=lambda path: video_client,
    )

    service.process_video("sample.mp4")

    timestamps = [
        item.timestamp_seconds
        for item in orchestrator.received_inputs
    ]

    assert timestamps == pytest.approx([0.0, 1 / 30, 2 / 30])


def test_process_video_releases_video_after_processing_error():
    video_client = FakeVideoClient("sample.mp4")

    class FailingOrchestrator:
        def process_frame(self, data):
            raise RuntimeError("Frame processing failed.")

    service = VideoProcessingService(
        orchestrator=FailingOrchestrator(),
        video_client_factory=lambda path: video_client,
    )

    with pytest.raises(RuntimeError, match="Frame processing failed"):
        service.process_video("sample.mp4")

    assert video_client.released is True


def test_process_video_rejects_invalid_fps():
    video_client = FakeVideoClient("sample.mp4")
    video_client.fps = 0.0

    orchestrator = FakeOrchestrator()

    service = VideoProcessingService(
        orchestrator=orchestrator,
        video_client_factory=lambda path: video_client,
    )

    with pytest.raises(ValueError, match="Video FPS"):
        service.process_video("sample.mp4")

    assert video_client.released is True
    assert orchestrator.received_inputs == []
