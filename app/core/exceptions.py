class TrafficSystemError(Exception):
    """Base exception for the traffic monitoring application."""


class ConfigurationError(TrafficSystemError):
    """Raised when application configuration is invalid."""


class VideoProcessingError(TrafficSystemError):
    """Raised when video processing fails."""


class DetectionError(TrafficSystemError):
    """Raised when vehicle detection fails."""


class TrackingError(TrafficSystemError):
    """Raised when vehicle tracking fails."""


class SpeedCalculationError(TrafficSystemError):
    """Raised when vehicle speed calculation fails."""


class OCRProcessingError(TrafficSystemError):
    """Raised when number plate recognition fails."""


class RepositoryError(TrafficSystemError):
    """Raised when database or file repository operations fail."""


class ResourceNotFoundError(TrafficSystemError):
    """Raised when a requested resource does not exist."""
