"""FastAPI application entry point."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.util import find_spec
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.dependencies import get_frame_orchestrator
from app.core.logging import get_logger, setup_logging
from app.db.init_db import init_db
from app.middlewares.request_context import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    register_exception_handlers,
)
from app.routers.video_router import router as video_router
from app.routers.violation_router import router as violation_router

settings = get_settings()
setup_logging(settings)
logger = get_logger("traffic_speed_system")


def _warm_up_models() -> None:
    """Load YOLO and EasyOCR in the background so the first upload is fast."""
    started = time.perf_counter()
    try:
        get_frame_orchestrator()
    except Exception:  # The first video will report the real error.
        logger.exception("Model warm-up failed")
        return
    logger.info("Vision models ready in %.1f s", time.perf_counter() - started)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare folders, database tables and models before serving requests."""
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_output_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    if settings.preload_models:
        Thread(target=_warm_up_models, name="model-warm-up", daemon=True).start()
    logger.info("Traffic Speed System API started")
    yield
    logger.info("Traffic Speed System API stopped")


app = FastAPI(
    title="Traffic Speed and Number Plate System",
    version="1.1.0",
    description="Computer vision based traffic speed and number plate detection API.",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)

register_exception_handlers(app)

app.include_router(violation_router)
app.include_router(video_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Report that the API is running."""
    return {"status": "healthy"}


def helmet_check_available() -> bool:
    """True when the helmet model file and its runtime are both present."""
    path = settings.resolved_helmet_model_path
    if not settings.helmet_detection_enabled or not path.is_file():
        return False
    return path.suffix.lower() != ".onnx" or find_spec("onnxruntime") is not None


@app.get("/api/v1/config", tags=["Health"])
def public_config() -> dict[str, float | int | str]:
    """Expose non-secret pipeline settings used by the dashboard."""
    return {
        "speed_limit_kmh": float(settings.speed_limit_kmh),
        "real_distance_meters": float(settings.real_distance_meters),
        "line_1_y": settings.line_1_y,
        "line_2_y": settings.line_2_y,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_video_extensions": ",".join(sorted(settings.video_extensions)),
        "helmet_check_available": int(helmet_check_available()),
    }


# Serve the built dashboard from the same server, so the whole system
# runs from one link (http://localhost:8000). Mounted last so API routes win.
_frontend_dir = settings.resolved_frontend_dist_dir
if (_frontend_dir / "index.html").is_file():
    app.mount(
        "/",
        StaticFiles(directory=_frontend_dir, html=True),
        name="dashboard",
    )
else:
    logger.warning(
        "Dashboard build not found at %s - run 'npm run build' in frontend/",
        _frontend_dir,
    )
