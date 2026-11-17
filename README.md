# Raftaar — Traffic Speed & Number Plate Recognition System

**A computer vision traffic monitoring system that detects vehicles, measures their speed, reads the number plates of speeders and explains the result through a voice assistant.**

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Detection-purple)
![ByteTrack](https://img.shields.io/badge/ByteTrack-Tracking-orange)
![OpenCV](https://img.shields.io/badge/OpenCV-Video-green?logo=opencv&logoColor=white)
![EasyOCR](https://img.shields.io/badge/EasyOCR-Plates-red)
![React](https://img.shields.io/badge/React-Dashboard-61dafb?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/Tests-58%20Passed-brightgreen)

> This is a computer vision project, **not** an LLM project. The voice assistant is rule-based and runs in the browser; every number it says comes from the backend API.

---

## Table of Contents

1. [Quick Start — One Link](#1-quick-start--one-link)
2. [Features](#2-features)
3. [Technology Stack](#3-technology-stack)
4. [System Architecture](#4-system-architecture)
5. [Processing Workflow](#5-processing-workflow)
6. [Dashboard and Raftaar Voice Assistant](#6-dashboard-and-raftaar-voice-assistant)
7. [Project Structure](#7-project-structure)
8. [Manual Installation](#8-manual-installation)
9. [Environment Configuration](#9-environment-configuration)
10. [Computer Vision Components](#10-computer-vision-components)
11. [Speed Estimation Methodology](#11-speed-estimation-methodology)
12. [Number Plate Recognition](#12-number-plate-recognition)
13. [REST API](#13-rest-api)
14. [Database Design](#14-database-design)
15. [Testing and Code Quality](#15-testing-and-code-quality)
16. [Limitations](#16-limitations)
17. [Future Enhancements](#17-future-enhancements)

---

# 1. Quick Start — One Link

The whole system (dashboard, voice assistant, API and annotated videos) runs from a single server.

**Windows:** double-click **`run.bat`** in the project folder.

It will:

1. Create the Python virtual environment and install dependencies (first run only).
2. Build the React dashboard into `frontend/dist` (only when it is missing).
3. Start FastAPI and open **http://localhost:8000** in your browser.

```text
run.bat            normal start
run.bat rebuild    rebuild the dashboard after frontend changes
set PORT=9000      (before run.bat) use another port
```

Stop the server with **Ctrl+C** in the console window.

> Run `run.bat` from the project folder or by double-click. Typing just `run` in another folder may start a different `run.bat` that happens to be on your `PATH`.

**Requirements:** Python 3.11+, Node.js 18+ (for the dashboard build), FFmpeg (for browser-playable H.264 output) and the YOLOv8 weights at `weights/yolov8n.pt`.

| Link | What it is |
|---|---|
| http://localhost:8000 | Dashboard with the Raftaar assistant |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/health | Health check |

---

# 2. Features

| Feature | Description |
|---|---|
| Video upload | Drag-and-drop MP4 / AVI / MOV / MKV upload with size and format validation |
| Background processing | Videos are processed in a background job with live progress polling |
| Vehicle detection | YOLOv8, restricted to configurable vehicle classes (car, motorcycle, bus, truck) |
| Tracking | ByteTrack keeps a stable ID per vehicle; pedestrians and other classes are ignored |
| Speed estimation | Time between two virtual lines with sub-frame crossing interpolation |
| Plate recognition | EasyOCR on the lower vehicle crop with CLAHE enhancement and plate validation |
| Late plate back-fill | A plate read *after* a violation was saved is written back to that violation |
| Violation records | Overspeeding vehicles are stored in SQLite automatically |
| Annotated video | Boxes, IDs, speeds, plates, speed lines and a live HUD, encoded as H.264 |
| Dashboard | Speed board with limit marker, plate cards, violation tickets, agent pipeline view |
| Voice assistant | "Raftaar" robot that listens, talks and answers questions about the result in English, Roman Urdu or Urdu script |
| Statistics | All-time violation statistics endpoint |
| Observability | Request-ID header, access logs and JSON error handling middleware |
| Configuration | Everything configurable through environment variables |

---

# 3. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+, JavaScript (React 19) |
| API | FastAPI, Uvicorn, Pydantic, Pydantic Settings |
| Computer vision | Ultralytics YOLOv8, ByteTrack, OpenCV, NumPy |
| OCR | EasyOCR |
| Video encoding | FFmpeg (libx264) |
| Database | SQLAlchemy 2 ORM, SQLite |
| Dashboard | React, Vite, Framer Motion, Lucide icons |
| Voice | Browser Web Speech API (`speechSynthesis`, `SpeechRecognition`), with no extra packages or cloud service |
| Quality | Pytest, Ruff, oxlint |

---

# 4. System Architecture

The project follows the layered architecture defined in `CLAUDE.md`.

```text
 Browser (React dashboard + Raftaar assistant)
            │  HTTP (same origin: http://localhost:8000)
            ▼
 middlewares/  request ID · access log · error → JSON
            ▼
 routers/      video_router · violation_router         (HTTP only)
            ▼
 services/     VideoJobService · VideoProcessingService · ViolationService
            │         │
            │         ▼
            │   orchestrators/ FrameOrchestrator  (per frame)
            │         ├─► TrackingAgent  (YOLOv8 + ByteTrack)
            │         ├─► SpeedAgent     (two-line timing)
            │         └─► PlateAgent     (EasyOCR)
            │                    ▲
            │         clients/  YOLODetectorClient · EasyOCRClient · VideoClient
            ▼
 repositories/ ViolationRepository ──► models/ VehicleViolation ──► db/ SQLite
```

| Layer | Responsibility |
|---|---|
| `core/` | Settings from environment, logging, domain exceptions, dependencies |
| `middlewares/` | Request ID, request logging, global error handling |
| `routers/` | HTTP endpoints only, mapping domain errors to status codes |
| `schemas/` | Pydantic request / response models |
| `services/` | Business logic: upload handling, background jobs, result aggregation, statistics |
| `orchestrators/` | Run the agents for each frame and combine their output |
| `agents/` | One computer vision responsibility each; they never call each other or persist data |
| `clients/` | Wrappers around YOLO, EasyOCR and OpenCV |
| `repositories/` | Database access |
| `models/` / `db/` | SQLAlchemy entities, engine and sessions |

The frame orchestrator uses the TrackingAgent's YOLO `track()` call for detection and tracking together, so YOLO runs only once per frame. `DetectionAgent` remains available as an independent detection component.

---

# 5. Processing Workflow

1. **Upload.** `POST /api/v1/videos/process` validates the extension and size, streams the file to `UPLOAD_DIR` and returns a `processing_id` with HTTP 202.
2. **Background job.** `VideoJobService` runs the pipeline in a daemon thread and updates progress in the in-memory job store.
3. **Per frame.** `FrameOrchestrator` calls:
   - `TrackingAgent`, which returns tracked vehicles with stable IDs;
   - `SpeedAgent`, which returns a speed once a vehicle has crossed both lines;
   - `PlateAgent`, which returns plate readings (OCR every `OCR_FRAME_INTERVAL` frames, then cached per track).
4. **Aggregation.** The service collects vehicle types, speeds and plates, saves a violation the first time a vehicle exceeds `SPEED_LIMIT_KMH`, and back-fills the plate if it is read later.
5. **Annotation.** Every frame is drawn with boxes, labels, plates, speed lines and a HUD, then FFmpeg converts the result to browser-compatible H.264.
6. **Result.** The status endpoint returns the final result. The dashboard shows it and Raftaar announces it.

Uploaded source videos are deleted after processing; temporary OpenCV files are always cleaned up, even on failure.

---

# 6. Dashboard and Raftaar Voice Assistant

The dashboard (`frontend/`) is a React app that FastAPI serves from `frontend/dist`.

**Sections:** live backend status, speed-limit sign, stat cards, video upload with progress, agent pipeline view, annotated output player with download, speed board, number plate cards and violation tickets.

## Raftaar assistant

The robot in the bottom-right corner is an animated SVG whose face shows its state: idle, listening, thinking, speaking, happy (no violations) or alert (violations found).

| Capability | How |
|---|---|
| Talks | `speechSynthesis`; can be muted, and every message has a replay button |
| Listens | `SpeechRecognition` via the mic button (Chrome / Edge; asks for microphone permission) |
| Languages | **UR** mode (Roman Urdu replies, Urdu speech recognition) and **EN** mode |
| Auto announcements | Speaks when a video is selected, when processing starts, when it finishes and if it fails |
| Commands | "start / shuru karo", "upload", "show video / video dikhao", "stop / chup" |

Example questions: *"result batao"*, *"kitni violations?"*, *"sab se tez gaari"*, *"average speed"*, *"number plates"*, *"how many cars"*, *"speed limit"*, *"total history"*, or a plate number such as *"LEA1234"*.

The assistant logic lives in `frontend/src/assistant/assistantBrain.js`. It matches keywords to intents and builds answers from the API result only. It contains no language model or prompt.

## Frontend development

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, API calls go to http://localhost:8000
npm run build      # production build served by FastAPI
npm run lint
```

`VITE_API_BASE_URL` (see `frontend/.env.example`) overrides the API location.

---

# 7. Project Structure

```text
traffic-speed-system/
├── app/
│   ├── agents/            base_agent, detection_agent, tracking_agent, speed_agent, plate_agent
│   ├── clients/           detector_client, yolo_detector_client, ocr_client, easyocr_client, video_client
│   ├── core/              config, dependencies, exceptions, logging
│   ├── db/                base, session, init_db
│   ├── middlewares/       request_context (request ID, logging, error handlers)
│   ├── models/            vehicle_violation
│   ├── orchestrators/     frame_orchestrator
│   ├── repositories/      violation_repository
│   ├── routers/           video_router, violation_router
│   ├── schemas/           video, violation
│   ├── services/          video_job_service, video_processing_service,
│   │                      video_progress_manager, violation_service
│   └── main.py            app factory, lifespan, dashboard mount
├── frontend/
│   └── src/
│       ├── api/           trafficApi.js
│       ├── assistant/     assistantBrain.js (rule-based intents)
│       ├── components/    RobotFace, RobotAssistant, ResultsPanel
│       ├── hooks/         useVideoAnalysis, useSpeech
│       ├── App.jsx, App.css, index.css, config.js
├── tests/
│   ├── unit/
│   └── integration/
├── data/                  videos/ (uploads), outputs/ (annotated), traffic.db
├── weights/               yolov8n.pt
├── run.bat                one-click launcher
├── .env.example
├── pyproject.toml
└── CLAUDE.md
```

---

# 8. Manual Installation

Use these steps if you are not on Windows or prefer to run each part yourself.

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1      Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cp .env.example .env            # Windows: Copy-Item .env.example .env

cd frontend && npm install && npm run build && cd ..

uvicorn app.main:app --reload   # then open http://localhost:8000
```

Database tables and the upload / output folders are created automatically on startup. `python -m app.db.init_db` still works for creating tables manually.

---

# 9. Environment Configuration

All settings come from environment variables or `.env` (see `.env.example`). Relative paths are resolved against the project root.

| Variable | Default | Description |
|---|---|---|
| `YOLO_MODEL_PATH` | `weights/yolov8n.pt` | YOLO model file |
| `CONFIDENCE_THRESHOLD` | `0.4` | Detection / tracking confidence |
| `VEHICLE_CLASSES` | `car,motorcycle,bus,truck` | COCO classes treated as vehicles |
| `SPEED_LIMIT_KMH` | `60` | Speed limit for violations |
| `LINE_1_Y` | `300` | First virtual line (pixel row) |
| `LINE_2_Y` | `500` | Second virtual line; must be greater than `LINE_1_Y` |
| `REAL_DISTANCE_METERS` | `10` | Real road distance between the lines |
| `OCR_LANGUAGES` | `en` | Comma-separated EasyOCR languages |
| `OCR_FRAME_INTERVAL` | `10` | Run OCR every N frames |
| `OCR_MIN_CONFIDENCE` | `0.25` | Minimum OCR confidence for a candidate |
| `OCR_USE_GPU` | `false` | Use GPU for EasyOCR |
| `UPLOAD_DIR` | `data/videos` | Temporary upload folder |
| `MAX_UPLOAD_SIZE_MB` | `500` | Upload size limit |
| `ALLOWED_VIDEO_EXTENSIONS` | `.mp4,.avi,.mov,.mkv` | Accepted upload formats |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed origins for the Vite dev server |
| `FRONTEND_DIST_DIR` | `frontend/dist` | Built dashboard served at `/` |
| `DATABASE_URL` | `sqlite:///data/traffic.db` | Database URL |
| `OUTPUT_DIR` | `data/outputs` | Annotated video folder |
| `LOG_LEVEL` | `INFO` | Logging level |

> The line positions, distance and limit are example values. Calibrate them for each camera; see [11.5](#115-calibration).

---

# 10. Computer Vision Components

| Component | File | Responsibility |
|---|---|---|
| VideoClient | `app/clients/video_client.py` | OpenCV frame reader with FPS, size and timestamps |
| YOLODetectorClient | `app/clients/yolo_detector_client.py` | Loads YOLOv8 and returns structured detections |
| EasyOCRClient | `app/clients/easyocr_client.py` | Plate-character OCR with a confidence filter |
| DetectionAgent | `app/agents/detection_agent.py` | Detects vehicles only (configured classes) |
| TrackingAgent | `app/agents/tracking_agent.py` | YOLOv8 + ByteTrack with persistent IDs; drops non-vehicles |
| SpeedAgent | `app/agents/speed_agent.py` | Line crossings, interpolation, km/h, overspeed flag |
| PlateAgent | `app/agents/plate_agent.py` | Plate crop, enhancement, OCR, validation, per-track cache |
| FrameOrchestrator | `app/orchestrators/frame_orchestrator.py` | Runs the agents per frame and combines the output |

Every agent receives and returns frozen dataclasses and never saves files or database records.

---

# 11. Speed Estimation Methodology

## 11.1 Principle

Two horizontal virtual lines are placed in the frame at `LINE_1_Y` and `LINE_2_Y`. The bottom edge of each tracked vehicle's box is followed from frame to frame.

## 11.2 Crossing-time interpolation

When the box bottom moves from `y_prev` (time `t_prev`) to `y_curr` (time `t_curr`) across a line at `y_line`:

```text
t_cross = t_prev + (y_line − y_prev) / (y_curr − y_prev) × (t_curr − t_prev)
```

This gives sub-frame accuracy instead of snapping to the nearest frame.

## 11.3 Speed

```text
Δt     = |t_line2 − t_line1|
v_km/h = REAL_DISTANCE_METERS / Δt × 3.6
```

A vehicle is overspeeding when `v_km/h > SPEED_LIMIT_KMH`. Each track is measured once.

## 11.4 Direction

Crossings are detected in both directions, so approaching and receding traffic are both measured.

## 11.5 Calibration

Accuracy depends on the real distance between the lines, a fixed camera, line placement where vehicles are fully visible, and reliable FPS. Short clips or slow traffic may produce no speeds if no vehicle crosses both lines; adjust `LINE_1_Y` / `LINE_2_Y` for the camera angle.

---

# 12. Number Plate Recognition

1. **Region.** The lower half of the vehicle box, with a 3% side margin.
2. **Enhancement.** 2× cubic upscale, grayscale, CLAHE contrast.
3. **OCR.** EasyOCR with an `A–Z 0–9` allowlist, keeping candidates above `OCR_MIN_CONFIDENCE`.
4. **Validation.** Uppercase, non-alphanumerics removed, 4–12 characters, at least one letter and one digit.
5. **Selection.** Candidates are voted per track (ties go to the longer text); the accepted plate is cached for that track.
6. **Back-fill.** If the plate is read after the violation was stored, the stored record is updated.

OCR results are recognition candidates, not legal identification. Quality depends on resolution, angle, lighting, motion blur and regional plate formats.

---

# 13. REST API

Base URL: `http://localhost:8000`. Every response carries an `X-Request-ID` header; errors are JSON.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/config` | Public pipeline settings (limit, lines, upload rules) |
| POST | `/api/v1/videos/process` | Upload a video (multipart `file`); returns `202` + `processing_id` |
| GET | `/api/v1/videos/{id}/status` | Progress, error and final result |
| GET | `/api/v1/videos/{id}/output` | Annotated H.264 MP4 (`409` until complete) |
| POST | `/api/v1/violations` | Create a violation manually |
| GET | `/api/v1/violations?limit=&offset=` | Paginated violations |
| GET | `/api/v1/violations/stats` | All-time statistics |
| GET | `/api/v1/violations/{id}` | One violation (`404` if missing) |

Upload errors: `415` unsupported format, `413` too large, `400` empty file.

**Completed job result (abridged):**

```json
{
  "status": "completed",
  "progress_percent": 100.0,
  "result": {
    "filename": "traffic.mp4",
    "fps": 30.0, "width": 1920, "height": 1080,
    "total_frames": 660, "processed_frames": 660,
    "duration_seconds": 22.0, "processing_seconds": 95.4,
    "speed_limit_kmh": 60.0,
    "vehicles_tracked": 18,
    "vehicle_types": {"car": 15, "truck": 3},
    "speed_records": [
      {"track_id": 7, "speed_kmh": 85.0, "is_overspeeding": true,
       "vehicle_type": "car", "plate_number": "ABC123"}
    ],
    "average_speed_kmh": 62.5, "max_speed_kmh": 85.0,
    "violations_saved": 1,
    "violations": [{"id": 1, "track_id": 7, "plate_number": "ABC123",
                    "speed_kmh": 85.0, "speed_limit_kmh": 60.0,
                    "violation_time": "2026-11-17T10:00:00Z",
                    "video_source": "traffic.mp4"}],
    "plates_identified": 1,
    "recognized_plates": [{"track_id": 7, "plate_number": "ABC123"}],
    "output_video_url": "/api/v1/videos/<id>/output"
  }
}
```

Interactive docs: `/docs` (Swagger) and `/redoc`.

---

# 14. Database Design

Table `vehicle_violations` (`app/models/vehicle_violation.py`):

| Field | Description |
|---|---|
| `id` | Primary key |
| `track_id` | ByteTrack vehicle ID |
| `plate_number` | Recognized plate (nullable, back-filled when read later) |
| `speed_kmh` | Measured speed |
| `speed_limit_kmh` | Limit at the time of the violation |
| `violation_time` | UTC timestamp (returned with a `Z` / `+00:00` offset) |
| `video_source` | Original video filename |

Repository operations: create, get by ID, list with pagination, count, update plate and aggregate statistics.

---

# 15. Testing and Code Quality

```bash
pytest -q                 # 58 tests: unit + integration
ruff check app tests      # lint
cd frontend && npm run lint && npm run build
```

Coverage includes all four agents, the orchestrator, video processing service, video job API (upload, late plate back-fill, failures, size / format / empty validation), violation repository / service / router / schemas, statistics, configuration parsing and the request middleware.

Latest verification:

| Check | Result |
|---|---|
| Pytest | 58 passed |
| Ruff | All checks passed |
| oxlint | No warnings |
| Vite build | Successful |
| Real clip through the API | Completed; annotated H.264 video generated |

---

# 16. Limitations

- **Calibration.** Speed accuracy depends on correct line placement and real-world distance per camera.
- **Processing speed.** CPU-only inference is slow for 1080p (roughly a minute or more per few seconds of video); a CUDA GPU helps significantly.
- **OCR.** Small, blurred or angled plates are often not readable.
- **Job store.** Job progress is kept in memory, so a server restart forgets running jobs (saved violations stay in the database).
- **Voice.** Speech recognition needs Chrome or Edge and microphone permission; available voices depend on the operating system.
- **Security.** There is no authentication; the API is intended for local use.

---

# 17. Future Enhancements

1. Live RTSP / webcam streams.
2. Perspective (homography) calibration instead of horizontal lines.
3. A dedicated plate detector before OCR.
4. Persistent job queue (e.g. database-backed) for restarts and parallel jobs.
5. Authentication and role-based access.
6. Reports and exports of violation history.
7. Docker packaging for deployment.

---

## Acknowledgements

[FastAPI](https://fastapi.tiangolo.com/) · [Ultralytics YOLO](https://docs.ultralytics.com/) · [ByteTrack](https://github.com/ifzhang/ByteTrack) · [OpenCV](https://opencv.org/) · [EasyOCR](https://github.com/JaidedAI/EasyOCR) · [SQLAlchemy](https://www.sqlalchemy.org/) · [Pydantic](https://docs.pydantic.dev/) · [React](https://react.dev/) · [Vite](https://vite.dev/)

No license has been specified yet; add one before distributing the software publicly.
