import logging
import logging.config

from app.core.config import Settings, get_settings


def setup_logging(settings: Settings | None = None) -> None:
    """Configure centralized application logging."""

    if settings is None:
        settings = get_settings()

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s | %(levelname)s | "
                    "%(name)s | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": settings.log_level,
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Return a named application logger."""
    return logging.getLogger(name)
