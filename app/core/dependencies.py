import logging
from functools import lru_cache

from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Provide application settings through dependency injection."""
    return get_settings()


@lru_cache(maxsize=1)
def get_app_logger() -> logging.Logger:
    """Provide the main application logger."""
    return logging.getLogger("traffic_speed_system")
