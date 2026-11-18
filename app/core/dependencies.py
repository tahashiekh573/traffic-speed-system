"""Shared, lazily created application dependencies."""

import logging
import os
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from app.orchestrators.frame_orchestrator import FrameOrchestrator

_orchestrator_lock = Lock()


def get_app_settings() -> Settings:
    """Provide application settings through dependency injection."""
    return get_settings()


@lru_cache(maxsize=1)
def get_app_logger() -> logging.Logger:
    """Provide the main application logger."""
    return logging.getLogger("traffic_speed_system")


def configure_torch_threads(settings: Settings | None = None) -> int:
    """Let PyTorch use the configured number of CPU threads."""
    settings = settings or get_settings()
    threads = settings.torch_threads or (os.cpu_count() or 1)

    import torch  # Imported lazily: heavy, and only needed for inference.

    torch.set_num_threads(threads)
    return threads


@lru_cache(maxsize=1)
def _build_frame_orchestrator() -> "FrameOrchestrator":
    from app.orchestrators.frame_orchestrator import FrameOrchestrator

    configure_torch_threads()
    return FrameOrchestrator()


def get_frame_orchestrator() -> "FrameOrchestrator":
    """Return the shared pipeline, loading YOLO and EasyOCR only once.

    Loading the models takes several seconds, so they are reused for every
    video. Callers must call ``reset()`` before each new video and process
    one video at a time.
    """
    with _orchestrator_lock:
        return _build_frame_orchestrator()
