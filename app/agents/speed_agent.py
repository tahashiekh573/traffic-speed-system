
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

        line1 = float(self.settings.line_1_y)
        line2 = float(self.settings.line_2_y)

        if line1 == line2:
            raise ValueError(
                "Speed measurement lines must be different."
            )

        self._line_positions = {
            1: line1,
            2: line2,
        }

        self._previous_observations: dict[
            int, tuple[float, float]
        ] = {}

        self._crossings: dict[
            int, dict[int, float]
        ] = {}

        self._completed_tracks: set[int] = set()

    @staticmethod
    def _crossing_time(
        previous_y: float,
        current_y: float,
        previous_time: float,
        current_time: float,
        line_y: float,
    ) -> float | None:
        """Interpolate the exact time when a vehicle crosses a line."""

        crossed = (
            previous_y < line_y <= current_y
            or previous_y > line_y >= current_y
        )

        if not crossed:
            return None

        if current_y == previous_y:
            return None

        fraction = (
            (line_y - previous_y)
            / (current_y - previous_y)
        )

        return previous_time + fraction * (
            current_time - previous_time
        )

    def _calculate_speed(
        self,
        first_crossing: float,
        second_crossing: float,
    ) -> float | None:
        """Calculate speed from the time between both lines."""

        elapsed_seconds = abs(
            second_crossing - first_crossing
        )

        if elapsed_seconds <= 0:
            return None

        distance_meters = float(
            self.settings.real_distance_meters
        )

        speed_kmh = (
            distance_meters / elapsed_seconds * 3.6
        )

        if not isfinite(speed_kmh) or speed_kmh <= 0:
            return None

        return speed_kmh

    def run(self, data: SpeedInput) -> SpeedOutput:
        timestamp = float(data.timestamp_seconds)

        if not isfinite(timestamp) or timestamp < 0:
            raise ValueError(
                "Timestamp must be finite and non-negative."
            )

        measurements = []

        for track in data.tracks:
            track_id = int(track.track_id)

            if track_id in self._completed_tracks:
                continue

            current_y = float(track.bbox[3])

            if not isfinite(current_y):
                continue

            previous = self._previous_observations.get(
                track_id
            )

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

            # Detect crossings of both lines.
            track_crossings = self._crossings.setdefault(
                track_id,
                {},
            )

            for line_number, line_y in (
                self._line_positions.items()
            ):
                crossing_time = self._crossing_time(
                    previous_y=previous_y,
                    current_y=current_y,
                    previous_time=previous_time,
                    current_time=timestamp,
                    line_y=line_y,
                )

                if (
                    crossing_time is not None
                    and line_number not in track_crossings
                ):
                    track_crossings[line_number] = (
                        crossing_time
                    )

            # Calculate speed after both lines are crossed.
            if (
                1 in track_crossings
                and 2 in track_crossings
            ):
                speed_kmh = self._calculate_speed(
                    track_crossings[1],
                    track_crossings[2],
                )

                if speed_kmh is not None:
                    speed_limit = float(
                        self.settings.speed_limit_kmh
                    )

                    measurements.append(
                        SpeedMeasurement(
                            track_id=track_id,
                            speed_kmh=round(speed_kmh, 2),
                            is_overspeeding=(
                                speed_kmh > speed_limit
                            ),
                        )
                    )

                    self._completed_tracks.add(track_id)

            self._previous_observations[track_id] = (
                current_y,
                timestamp,
            )

        return SpeedOutput(
            measurements=measurements
        )
