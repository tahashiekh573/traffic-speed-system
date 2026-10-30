from dataclasses import dataclass
from math import isfinite

from app.agents.base_agent import BaseAgent
from app.agents.tracking_agent import TrackedObject
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class SpeedInput:
    tracks: list[TrackedObject]
    timestamp_seconds: float


@dataclass(frozen=True)
class SpeedMeasurement:
    track_id: int
    speed_kmh: float
    is_overspeeding: bool


@dataclass(frozen=True)
class SpeedOutput:
    measurements: list[SpeedMeasurement]


class SpeedAgent(BaseAgent[SpeedInput, SpeedOutput]):
    """Calculate vehicle speed using two virtual counting lines."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        if self.settings.line_1_y == self.settings.line_2_y:
            raise ValueError("Speed measurement lines must be different.")

        self._previous_observations: dict[int, tuple[float, float]] = {}
        self._line1_crossings: dict[int, float] = {}
        self._completed_tracks: set[int] = set()

    @staticmethod
    def _crossing_time(
        previous_y: float,
        current_y: float,
        previous_time: float,
        current_time: float,
        line_y: float,
    ) -> float | None:
        crossed = (
            previous_y < line_y <= current_y
            or previous_y > line_y >= current_y
        )

        if not crossed:
            return None

        if current_y == previous_y:
            return None

        fraction = (line_y - previous_y) / (current_y - previous_y)

        return previous_time + fraction * (current_time - previous_time)

    def run(self, data: SpeedInput) -> SpeedOutput:
        timestamp = float(data.timestamp_seconds)

        if not isfinite(timestamp) or timestamp < 0:
            raise ValueError("Timestamp must be finite and non-negative.")

        measurements = []

        for track in data.tracks:
            track_id = int(track.track_id)

            if track_id in self._completed_tracks:
                continue

            current_y = float(track.bbox[3])

            if not isfinite(current_y):
                continue

            previous = self._previous_observations.get(track_id)

            if previous is None:
                self._previous_observations[track_id] = (
                    current_y,
                    timestamp,
                )
                continue

            previous_y, previous_time = previous

            if timestamp <= previous_time:
                raise ValueError(
                    "Timestamps must increase for each tracked vehicle."
                )

            line1_time = self._crossing_time(
                previous_y,
                current_y,
                previous_time,
                timestamp,
                float(self.settings.line_1_y),
            )

            line2_time = self._crossing_time(
                previous_y,
                current_y,
                previous_time,
                timestamp,
                float(self.settings.line_2_y),
            )

            first_crossing = self._line1_crossings.get(track_id)

            if line1_time is not None and first_crossing is None:
                first_crossing = line1_time
                self._line1_crossings[track_id] = first_crossing

            if (
                first_crossing is not None
                and line2_time is not None
                and line2_time > first_crossing
            ):
                elapsed_seconds = line2_time - first_crossing

                speed_kmh = (
                    float(self.settings.real_distance_meters)
                    / elapsed_seconds
                    * 3.6
                )

                measurements.append(
                    SpeedMeasurement(
                        track_id=track_id,
                        speed_kmh=round(speed_kmh, 2),
                        is_overspeeding=(
                            speed_kmh > float(self.settings.speed_limit_kmh)
                        ),
                    )
                )

                self._completed_tracks.add(track_id)

            self._previous_observations[track_id] = (
                current_y,
                timestamp,
            )

        return SpeedOutput(measurements=measurements)
