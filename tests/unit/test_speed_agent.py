from types import SimpleNamespace

import pytest

from app.agents.speed_agent import SpeedAgent, SpeedInput
from app.agents.tracking_agent import TrackedObject


@pytest.fixture
def settings():
    return SimpleNamespace(
        line_1_y=100,
        line_2_y=200,
        real_distance_meters=15.0,
        speed_limit_kmh=15.0,
    )


def make_track(track_id, bottom_y):
    return TrackedObject(
        track_id=track_id,
        bbox=(10.0, 20.0, 100.0, float(bottom_y)),
        confidence=0.95,
        class_id=2,
        class_name="car",
    )


def test_speed_agent_calculates_vehicle_speed(settings):
    agent = SpeedAgent(settings=settings)

    first = agent.run(
        SpeedInput(
            tracks=[make_track(1, 90)],
            timestamp_seconds=0.0,
        )
    )
    assert first.measurements == []

    second = agent.run(
        SpeedInput(
            tracks=[make_track(1, 110)],
            timestamp_seconds=1.0,
        )
    )
    assert second.measurements == []

    third = agent.run(
        SpeedInput(
            tracks=[make_track(1, 190)],
            timestamp_seconds=3.0,
        )
    )
    assert third.measurements == []

    fourth = agent.run(
        SpeedInput(
            tracks=[make_track(1, 210)],
            timestamp_seconds=4.0,
        )
    )

    assert len(fourth.measurements) == 1

    measurement = fourth.measurements[0]

    assert measurement.track_id == 1
    assert measurement.speed_kmh == 18.0
    assert measurement.is_overspeeding is True


def test_speed_agent_does_not_repeat_completed_measurement(settings):
    agent = SpeedAgent(settings=settings)

    agent.run(SpeedInput([make_track(1, 90)], 0.0))
    agent.run(SpeedInput([make_track(1, 110)], 1.0))
    agent.run(SpeedInput([make_track(1, 190)], 3.0))

    result = agent.run(
        SpeedInput([make_track(1, 210)], 4.0)
    )

    assert len(result.measurements) == 1

    repeated = agent.run(
        SpeedInput([make_track(1, 220)], 5.0)
    )

    assert repeated.measurements == []


def test_speed_agent_rejects_identical_lines():
    invalid_settings = SimpleNamespace(
        line_1_y=100,
        line_2_y=100,
        real_distance_meters=15.0,
        speed_limit_kmh=50.0,
    )

    with pytest.raises(ValueError):
        SpeedAgent(settings=invalid_settings)


def test_speed_agent_rejects_invalid_timestamp(settings):
    agent = SpeedAgent(settings=settings)

    with pytest.raises(ValueError):
        agent.run(
            SpeedInput(
                tracks=[],
                timestamp_seconds=-1.0,
            )
        )

