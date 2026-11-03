from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.video_router import router as video_router
from app.routers.violation_router import router as violation_router

app = FastAPI(
    title="Traffic Speed and Number Plate System",
    version="0.1.0",
    description="Computer vision based traffic speed and number plate detection API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(violation_router)
app.include_router(video_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
