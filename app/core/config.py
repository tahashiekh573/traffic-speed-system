from functools import lru_cache
from pathlib import Path

from pydantic import Field, PositiveFloat, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # YOLO Configuration
    yolo_model_path: Path = Path("weights/yolov8n.pt")
    confidence_threshold: float = Field(default=0.4, gt=0.0, le=1.0)

    # Speed Detection
    speed_limit_kmh: PositiveFloat = 60.0
    line_1_y: int = Field(default=300, ge=0)
    line_2_y: int = Field(default=500, ge=0)
    real_distance_meters: PositiveFloat = 10.0

    # OCR Configuration
    ocr_languages: str = "en"

    # Database
    database_url: str = "sqlite:///data/traffic.db"

    # Output
    output_dir: Path = Path("data/outputs")

    # Logging
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure the logging level is supported."""
        normalized = value.upper()

        allowed_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if normalized not in allowed_levels:
            raise ValueError(
                f"Invalid log level: {value}. "
                f"Allowed values: {sorted(allowed_levels)}"
            )

        return normalized

    @field_validator("line_2_y")
    @classmethod
    def validate_line_positions(cls, value: int, info) -> int:
        """Ensure the second detection line follows the first."""
        line_1 = info.data.get("line_1_y")

        if line_1 is not None and value <= line_1:
            raise ValueError("LINE_2_Y must be greater than LINE_1_Y")

        return value

    def resolve_path(self, path: Path) -> Path:
        """Resolve relative paths against the project root."""
        if path.is_absolute():
            return path

        return (PROJECT_ROOT / path).resolve()

    @property
    def resolved_yolo_model_path(self) -> Path:
        """Return the absolute YOLO model path."""
        return self.resolve_path(self.yolo_model_path)

    @property
    def resolved_output_dir(self) -> Path:
        """Return the absolute output directory."""
        return self.resolve_path(self.output_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()
