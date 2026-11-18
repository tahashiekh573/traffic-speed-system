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
    # Speed lines: a value <= 1 is a fraction of the frame height
    # (0.55 = 55% down the frame) so they fit any resolution;
    # a value > 1 is an absolute pixel row.
    line_1_y: float = Field(default=0.55, ge=0)
    line_2_y: float = Field(default=0.80, ge=0)
    real_distance_meters: PositiveFloat = 10.0

    yolo_image_size: int = Field(default=640, ge=160, le=1920)

    # Tracking Configuration
    vehicle_classes: str = "car,motorcycle,bus,truck"

    # Performance
    # Run the vision pipeline at about this many frames per second of video
    # (0 = every frame). Skipped frames reuse the latest annotations.
    target_process_fps: float = Field(default=10.0, ge=0.0)
    torch_threads: int = Field(default=0, ge=0)  # 0 = all CPU cores
    preload_models: bool = True
    output_max_width: int = Field(default=1280, ge=0)  # 0 = original size
    preview_interval_seconds: float = Field(default=1.0, gt=0.0)

    # OCR Configuration
    ocr_languages: str = "en"
    ocr_frame_interval: int = Field(default=10, ge=1)
    ocr_min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    ocr_use_gpu: bool = False
    # "overspeeding" = read plates of speeders only (fast), "all" = every vehicle
    ocr_mode: str = "overspeeding"
    ocr_max_per_frame: int = Field(default=2, ge=1)
    ocr_max_attempts_per_track: int = Field(default=6, ge=1)
    ocr_min_box_height: int = Field(default=60, ge=0)
    ocr_max_crop_width: int = Field(default=360, ge=64)

    # Helmet check (needs a helmet detection model, see README)
    helmet_detection_enabled: bool = True
    helmet_model_path: Path = Path("weights/helmet.onnx")
    helmet_confidence: float = Field(default=0.35, gt=0.0, le=1.0)
    # Model class names meaning "rider wears a helmet" / "rider has no helmet".
    helmet_class_names: str = "helmet,with helmet,with_helmet,withhelmet"
    no_helmet_class_names: str = (
        "no helmet,no-helmet,no_helmet,without helmet,without_helmet,nohelmet,head"
    )
    helmet_rider_classes: str = "motorcycle"
    helmet_image_size: int = Field(default=320, ge=96, le=1280)
    helmet_votes_required: int = Field(default=3, ge=1)
    helmet_frame_interval: int = Field(default=3, ge=1)
    helmet_max_per_frame: int = Field(default=4, ge=1)
    helmet_min_box_height: int = Field(default=50, ge=0)

    # Video Upload
    upload_dir: Path = Path("data/videos")
    max_upload_size_mb: int = Field(default=500, gt=0)
    allowed_video_extensions: str = ".mp4,.avi,.mov,.mkv"

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Built dashboard served by FastAPI (npm run build -> frontend/dist)
    frontend_dist_dir: Path = Path("frontend/dist")

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

    @field_validator("ocr_mode")
    @classmethod
    def validate_ocr_mode(cls, value: str) -> str:
        """Allow only the supported OCR modes."""
        normalized = value.strip().lower()
        if normalized not in {"overspeeding", "all"}:
            raise ValueError("OCR_MODE must be 'overspeeding' or 'all'")
        return normalized

    @field_validator("line_2_y")
    @classmethod
    def validate_line_positions(cls, value: int, info) -> int:
        """Ensure the second detection line follows the first."""
        line_1 = info.data.get("line_1_y")

        if line_1 is not None and value <= line_1:
            raise ValueError("LINE_2_Y must be greater than LINE_1_Y")

        return value

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        """Split a comma separated environment value into clean items."""
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def vehicle_class_names(self) -> set[str]:
        """Return the lowercase vehicle class names to track."""
        return {name.lower() for name in self._split_csv(self.vehicle_classes)}

    @property
    def ocr_language_list(self) -> list[str]:
        """Return the configured EasyOCR languages."""
        return self._split_csv(self.ocr_languages) or ["en"]

    @property
    def video_extensions(self) -> set[str]:
        """Return the accepted upload extensions in lowercase."""
        return {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in self._split_csv(self.allowed_video_extensions)
        }

    @property
    def cors_origin_list(self) -> list[str]:
        """Return the allowed CORS origins."""
        return self._split_csv(self.cors_origins)

    @staticmethod
    def line_to_pixels(value: float, frame_height: int | None) -> float:
        """Convert a configured line position into a pixel row."""
        if value <= 1 and frame_height:
            return value * frame_height
        return float(value)

    def line_rows(self, frame_height: int | None) -> tuple[float, float]:
        """Return both speed-line rows in pixels for a frame height."""
        return (
            self.line_to_pixels(self.line_1_y, frame_height),
            self.line_to_pixels(self.line_2_y, frame_height),
        )

    def frame_stride(self, fps: float) -> int:
        """Return how many video frames to advance per pipeline run."""
        if self.target_process_fps <= 0 or fps <= 0:
            return 1
        return max(1, round(fps / self.target_process_fps))

    @property
    def max_upload_size_bytes(self) -> int:
        """Return the upload limit in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

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
    def resolved_upload_dir(self) -> Path:
        """Return the absolute upload directory."""
        return self.resolve_path(self.upload_dir)

    @property
    def resolved_helmet_model_path(self) -> Path:
        """Return the absolute helmet model path."""
        return self.resolve_path(self.helmet_model_path)

    @property
    def helmet_labels(self) -> set[str]:
        """Normalised model labels that mean 'helmet worn'."""
        names = self._split_csv(self.helmet_class_names)
        return {self.normalize_label(x) for x in names}

    @property
    def no_helmet_labels(self) -> set[str]:
        """Normalised model labels that mean 'no helmet'."""
        return {
            self.normalize_label(x) for x in self._split_csv(self.no_helmet_class_names)
        }

    @property
    def helmet_rider_class_names(self) -> set[str]:
        """Vehicle classes whose riders are checked for helmets."""
        return {x.lower() for x in self._split_csv(self.helmet_rider_classes)}

    @staticmethod
    def normalize_label(label: str) -> str:
        """Lowercase a class name and drop spaces, dashes and underscores."""
        return "".join(ch for ch in label.lower() if ch.isalnum())

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        """Return the absolute folder of the built dashboard."""
        return self.resolve_path(self.frontend_dist_dir)

    @property
    def resolved_output_dir(self) -> Path:
        """Return the absolute output directory."""
        return self.resolve_path(self.output_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()


