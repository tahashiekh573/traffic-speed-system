from fastapi import FastAPI

from app.routers.violation_router import router as violation_router

app = FastAPI(
    title="Traffic Speed and Number Plate System",
    version="0.1.0",
    description="Computer vision based traffic speed and number plate detection API.",
)

app.include_router(violation_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Check whether the API is running."""
    return {"status": "healthy"}
