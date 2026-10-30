# Traffic Speed & Number Plate Recognition System

**An Intelligent Computer Vision-Based Traffic Monitoring and Vehicle Violation Management System**

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Object%20Detection-purple)
![ByteTrack](https://img.shields.io/badge/ByteTrack-Object%20Tracking-orange)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-green?logo=opencv&logoColor=white)
![EasyOCR](https://img.shields.io/badge/EasyOCR-Text%20Recognition-red)
![Tests](https://img.shields.io/badge/Tests-39%20Passed-brightgreen)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Objectives](#2-project-objectives)
3. [Key Features](#3-key-features)
4. [Technology Stack](#4-technology-stack)
5. [System Architecture](#5-system-architecture)
6. [Processing Workflow](#6-processing-workflow)
7. [Project Structure](#7-project-structure)
8. [Installation and Setup](#8-installation-and-setup)
9. [Environment Configuration](#9-environment-configuration)
10. [Computer Vision Components](#10-computer-vision-components)
11. [Speed Estimation Methodology](#11-speed-estimation-methodology)
12. [Number Plate Recognition](#12-number-plate-recognition)
13. [REST API Documentation](#13-rest-api-documentation)
14. [Database Design](#14-database-design)
15. [Running the Application](#15-running-the-application)
16. [Testing and Code Quality](#16-testing-and-code-quality)
17. [Implementation Status](#17-implementation-status)
18. [Limitations](#18-limitations)
19. [Future Enhancements](#19-future-enhancements)

---

# 1. Project Overview

The **Traffic Speed & Number Plate Recognition System** is a modular computer vision-based application designed to support automated traffic monitoring and vehicle violation management.

The system combines vehicle detection, multi-object tracking, vehicle speed estimation, and number plate text recognition within a layered software architecture.

It uses **YOLOv8** for vehicle object detection, **ByteTrack** for maintaining vehicle identities across video frames, **OpenCV** for image processing, and **EasyOCR** for recognizing text from vehicle number plate regions.

A centralized frame orchestrator coordinates the computer vision agents. The backend uses **FastAPI** to expose REST endpoints for managing traffic violation records, while **SQLAlchemy** and **SQLite** provide structured database persistence.

The project is organized into independent clients, agents, orchestrators, services, repositories, database models, schemas, and API routers to support maintainability, testing, and future development.

## 1.1 Project Purpose

The primary purpose of this project is to establish a software foundation for computer vision-based traffic monitoring.

The implemented components focus on:

- Detecting vehicles in image frames.
- Tracking vehicles across consecutive frames.
- Estimating vehicle speed using calibrated detection lines.
- Extracting and normalizing vehicle number plate text.
- Coordinating frame-level computer vision processing.
- Managing structured traffic violation records.
- Providing REST API access to stored violation information.

## 1.2 Application Scope

The current implementation includes the computer vision agents, frame orchestration, database layer, violation management services, and REST API.

The project currently provides the core components required for vehicle analysis and violation record management.

A complete video upload and end-to-end video processing API, live camera streaming, and a graphical dashboard are not yet implemented.

---

# 2. Project Objectives

The system is designed around the following objectives.

## 2.1 Vehicle Detection

Use a YOLOv8 object detection model to identify vehicle objects in video frames.

## 2.2 Vehicle Tracking

Use ByteTrack to associate vehicle detections across consecutive frames and maintain consistent tracking identifiers.

## 2.3 Vehicle Speed Estimation

Estimate vehicle speed based on the time required for a tracked vehicle to move between two configured virtual detection lines.

## 2.4 Number Plate Recognition

Extract vehicle number plate regions and recognize alphanumeric text using EasyOCR.

## 2.5 Modular Processing

Separate detection, tracking, speed estimation, and optical character recognition responsibilities into independent components.

## 2.6 Violation Data Management

Provide structured database operations and REST API endpoints for creating, listing, and retrieving traffic violation records.

## 2.7 Maintainability and Testing

Use a layered architecture, dependency injection, data validation, and automated tests to make the application easier to maintain and extend.

---

# 3. Key Features

| Feature | Description |
|---|---|
| Vehicle Detection | YOLOv8-based vehicle object detection |
| Object Tracking | ByteTrack-based multi-object tracking |
| Speed Estimation | Speed calculation using two virtual detection lines |
| Number Plate OCR | Text extraction using EasyOCR |
| Text Normalization | Uppercase alphanumeric plate text normalization |
| Frame Orchestration | Coordination of tracking, speed, and plate agents |
| Violation Management | Creation and retrieval of traffic violation records |
| REST API | FastAPI-based API endpoints |
| Database Persistence | SQLAlchemy ORM with SQLite |
| Data Validation | Pydantic request and response schemas |
| Configuration Management | Environment-based application settings |
| Automated Testing | Unit and integration test coverage |
| Code Quality | Ruff linting and Python compilation checks |

---

# 4. Technology Stack

The application uses the following technologies.

| Technology | Role in the Project |
|---|---|
| Python 3.11+ | Main programming language |
| FastAPI | REST API framework |
| YOLOv8 | Vehicle object detection |
| ByteTrack | Multi-object tracking |
| OpenCV | Video and image processing |
| EasyOCR | Number plate text recognition |
| NumPy | Numerical and image-array operations |
| SQLAlchemy | Database object-relational mapping |
| SQLite | Relational database |
| Pydantic | Request and response data validation |
| Pydantic Settings | Environment-based configuration |
| Pytest | Unit and integration testing |
| Ruff | Code quality and linting |
| Uvicorn | ASGI application server |

---

# 5. System Architecture

The project follows a modular, layered architecture.

Each layer has a specific responsibility and communicates with the relevant application components.

## 5.1 High-Level Architecture

```text
                  VIDEO FRAME INPUT
                         |
                         v
                FRAME ORCHESTRATOR
                         |
                         v
                  TRACKING AGENT
                 (YOLOv8 + ByteTrack)
                         |
              +----------+----------+
              |                     |
              v                     v
         SPEED AGENT            PLATE AGENT
              |                     |
              v                     v
       SPEED ESTIMATION       PLATE EXTRACTION
              |                     |
              |                     v
              |                  EASY OCR
              |                     |
              +----------+----------+
                         |
                         v
               FRAME PROCESSING OUTPUT
                         |
                         v
                VIOLATION MANAGEMENT
                         |
                         v
                   FASTAPI ROUTER
                         |
                         v
                  VIOLATION SERVICE
                         |
                         v
                VIOLATION REPOSITORY
                         |
                         v
                   SQLALCHEMY ORM
                         |
                         v
                   SQLITE DATABASE
```

**Architecture note:** The frame orchestrator uses the TrackingAgent's YOLO tracking operation to perform detection and tracking together. This avoids running a separate duplicate YOLO inference for the same frame.

The frame-processing output and violation management API are implemented as separate application components. Automatic persistence of every orchestrated frame result is not yet integrated.

## 5.2 Architectural Layers

### Core Layer

Responsible for application configuration, logging, exceptions, and shared dependencies.

### Client Layer

Provides interfaces to external computer vision and OCR libraries.

### Agent Layer

Contains the main computer vision processing components:

- DetectionAgent
- TrackingAgent
- SpeedAgent
- PlateAgent

### Orchestration Layer

Coordinates frame-level processing and combines the outputs of the relevant agents.

### Schema Layer

Defines validated request and response structures using Pydantic.

### Service Layer

Contains application-level business logic for violation management.

### Repository Layer

Handles database operations and data access.

### Model Layer

Defines SQLAlchemy database models.

### Database Layer

Manages database connections, sessions, and table initialization.

### Router Layer

Exposes application functionality through REST API endpoints.

---

# 6. Processing Workflow

The current frame-processing workflow is organized into the following stages.

## Stage 1: Frame Input

An image frame is supplied to the frame orchestrator.

The orchestrator validates that the input is a valid, non-empty NumPy array.

## Stage 2: Vehicle Detection and Tracking

The TrackingAgent uses the YOLOv8 model with ByteTrack to identify vehicles and maintain their tracking IDs across frames.

## Stage 3: Speed Estimation

The SpeedAgent monitors tracked vehicle positions and determines when a vehicle crosses the configured virtual detection lines.

It uses interpolated crossing times to estimate the elapsed time between the two lines.

## Stage 4: Number Plate Processing

The PlateAgent extracts a plate-focused crop from the lower region of the vehicle bounding box and passes it to the OCR client.

## Stage 5: OCR Text Processing

EasyOCR identifies possible text candidates. The PlateAgent normalizes the recognized text and filters candidates according to the configured validation rules.

## Stage 6: Result Aggregation

The FrameOrchestrator combines the tracking, speed estimation, and number plate processing outputs into a frame-processing result.

## Stage 7: Violation Management

The FastAPI application provides endpoints for creating and retrieving structured violation records.

The API and database layers can manage violation records independently of the frame-processing workflow.

---

# 7. Project Structure

The repository is organized as follows:

```text
traffic-speed-system/
│
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── detection_agent.py
│   │   ├── tracking_agent.py
│   │   ├── speed_agent.py
│   │   └── plate_agent.py
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── video_client.py
│   │   ├── detector_client.py
│   │   ├── yolo_detector_client.py
│   │   ├── ocr_client.py
│   │   └── easyocr_client.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── init_db.py
│   │   └── session.py
│   │
│   ├── middlewares/
│   │   └── __init__.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── vehicle_violation.py
│   │
│   ├── orchestrators/
│   │   ├── __init__.py
│   │   └── frame_orchestrator.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── violation_repository.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   └── violation_router.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── violation.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── violation_service.py
│   │
│   └── main.py
│
├── data/
│   ├── videos/
│   └── outputs/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── weights/
│   └── yolov8n.pt
│
├── .env.example
├── .gitignore
├── CLAUDE.md
├── pyproject.toml
└── README.md
```

---

# 8. Installation and Setup

Follow these steps to configure the project locally.

## 8.1 Prerequisites

Ensure the following software is installed:

- Python 3.11 or newer
- Git
- pip
- A supported operating system
- Sufficient memory and processing resources for computer vision dependencies

## 8.2 Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
```

Navigate to the project directory:

```bash
cd traffic-speed-system
```

Replace the repository URL with the actual Git repository address.

## 8.3 Create a Virtual Environment

```bash
python -m venv .venv
```

## 8.4 Activate the Virtual Environment

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate the environment again.

**Linux or macOS:**

```bash
source .venv/bin/activate
```

## 8.5 Install Project Dependencies

Install the project and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

This installs the dependencies defined in `pyproject.toml`.

## 8.6 Configure Environment Variables

Create a local environment configuration file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update the values in `.env` according to the camera setup and application environment.

## 8.7 Verify the YOLO Model

Ensure the YOLOv8 model file is available at:

```text
weights/yolov8n.pt
```

The model path must match the `YOLO_MODEL_PATH` setting.

## 8.8 Initialize the Database

Run:

```bash
python -m app.db.init_db
```

This initializes the configured database and creates the required SQLAlchemy tables.

---

# 9. Environment Configuration

Application settings are managed through environment variables.

The following values are provided in `.env.example`.

| Variable | Default Value | Description |
|---|---|---|
| YOLO_MODEL_PATH | weights/yolov8n.pt | YOLO model file path |
| CONFIDENCE_THRESHOLD | 0.4 | Object detection confidence threshold |
| SPEED_LIMIT_KMH | 60 | Configured vehicle speed limit |
| LINE_1_Y | 300 | First virtual detection line position |
| LINE_2_Y | 500 | Second virtual detection line position |
| REAL_DISTANCE_METERS | 10 | Calibrated real-world distance between detection lines |
| OCR_LANGUAGES | en | OCR language configuration |
| DATABASE_URL | sqlite:///data/traffic.db | Database connection URL |
| OUTPUT_DIR | data/outputs | Application output directory |
| LOG_LEVEL | INFO | Application logging level |

**Important:** The default detection-line positions, speed limit, and real-world distance are example configuration values. They must be calibrated for the actual camera position and monitored road.

---

# 10. Computer Vision Components

## 10.1 Video Client

**File:** `app/clients/video_client.py`

The video client provides an OpenCV-based interface for video-related operations.

It acts as an abstraction layer between application components and OpenCV.

## 10.2 Detector Client

**File:** `app/clients/detector_client.py`

Defines the detection data structure and detector interface.

It helps separate detection logic from the underlying model implementation.

## 10.3 YOLO Detector Client

**File:** `app/clients/yolo_detector_client.py`

Provides integration with the Ultralytics YOLOv8 model.

Its responsibilities include:

- Loading the configured model.
- Performing object detection.
- Providing detection results to the application.
- Supporting the tracking integration used by the TrackingAgent.

## 10.4 DetectionAgent

**File:** `app/agents/detection_agent.py`

Responsible for vehicle detection-related processing through the detector abstraction.

It separates detection responsibilities from the rest of the application.

## 10.5 TrackingAgent

**File:** `app/agents/tracking_agent.py`

Uses YOLOv8 tracking with ByteTrack to maintain vehicle identities across frames.

Its responsibilities include:

- Processing image frames through the tracking model.
- Associating detected vehicles across frames.
- Maintaining tracking identifiers.
- Returning tracked vehicle information.

## 10.6 SpeedAgent

**File:** `app/agents/speed_agent.py`

Calculates vehicle speed using tracked vehicle movement between two virtual detection lines.

Its responsibilities include:

- Monitoring tracked vehicle positions.
- Detecting virtual-line crossings.
- Interpolating crossing timestamps.
- Calculating speed in kilometers per hour.
- Checking the configured speed limit.
- Avoiding duplicate completed measurements for the same track.

## 10.7 PlateAgent

**File:** `app/agents/plate_agent.py`

Processes vehicle bounding boxes to extract possible number plate regions.

Its responsibilities include:

- Extracting a crop from the lower portion of a vehicle bounding box.
- Sending the crop to the OCR client.
- Normalizing recognized text.
- Filtering invalid candidates.
- Returning a valid plate candidate when available.

## 10.8 OCR Client

**Files:**

- `app/clients/ocr_client.py`
- `app/clients/easyocr_client.py`

The OCR client abstraction separates text-recognition functionality from the PlateAgent.

EasyOCR provides the underlying optical character recognition implementation.

---

# 11. Speed Estimation Methodology

The SpeedAgent estimates vehicle speed using the time difference between two virtual detection-line crossings.

## 11.1 Basic Principle

Two virtual detection lines are configured in the camera frame.

When a tracked vehicle crosses the first line, the system records its crossing time.

When the same tracked vehicle crosses the second line, the system records the second crossing time.

The elapsed time is calculated as:

\[
\Delta t = t_2 - t_1
\]

Where:

- \(t_1\) is the first line crossing time.
- \(t_2\) is the second line crossing time.
- \(\Delta t\) is the elapsed time in seconds.

## 11.2 Speed Calculation

The speed is calculated using:

\[
v = \frac{d}{\Delta t}
\]

Where:

- \(v\) is speed in meters per second.
- \(d\) is the calibrated real-world distance in meters.
- \(\Delta t\) is elapsed time in seconds.

To convert meters per second into kilometers per hour:

\[
v_{km/h} = \frac{d}{\Delta t} \times 3.6
\]

## 11.3 Crossing-Time Interpolation

The SpeedAgent uses interpolation to estimate the crossing time when a vehicle moves between observed positions.

This helps estimate the time of line crossing more accurately than relying only on the timestamps of the nearest frames.

## 11.4 Speed Limit Evaluation

The calculated speed is compared against the configured speed limit.

A vehicle is treated as exceeding the configured limit when:

\[
v_{km/h} > v_{limit}
\]

The result includes the calculated speed and the speed-limit evaluation.

## 11.5 Calibration Requirements

Accurate speed estimation depends on:

- Correct real-world distance between the detection lines.
- Accurate camera placement.
- Stable camera position.
- Reliable frame timestamps.
- Appropriate detection-line placement.
- Consistent vehicle tracking.

The default configuration values are not universal traffic measurements. They must be calibrated for each deployment environment.

---

# 12. Number Plate Recognition

The number plate recognition component uses EasyOCR to extract alphanumeric text from vehicle images.

## 12.1 Plate Region Extraction

The PlateAgent receives vehicle bounding-box information and extracts a crop from the lower region of the vehicle bounding box.

This region is used as the input for OCR processing.

## 12.2 Optical Character Recognition

The EasyOCR client processes the cropped image and returns recognized text candidates.

## 12.3 Text Normalization

Recognized text is normalized by:

- Converting characters to uppercase.
- Removing non-alphanumeric characters.
- Filtering candidates according to the supported length rules.

The current validation accepts normalized candidates containing between 4 and 12 alphanumeric characters.

## 12.4 Candidate Selection

When multiple valid candidates are returned, the PlateAgent selects the longest valid candidate.

## 12.5 Recognition Limitations

Recognition quality depends on:

- Image resolution.
- Plate visibility.
- Lighting conditions.
- Camera angle.
- Motion blur.
- Plate cleanliness and physical condition.
- OCR language configuration.
- Regional number plate formats.

OCR results should be treated as recognition candidates rather than guaranteed legal identification.

---

# 13. REST API Documentation

The backend uses FastAPI to provide REST endpoints for traffic violation record management.

## 13.1 Base URL

When running locally:

```text
http://127.0.0.1:8000
```

## 13.2 Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check application health |
| POST | `/api/v1/violations` | Create a violation record |
| GET | `/api/v1/violations` | Retrieve violation records with pagination |
| GET | `/api/v1/violations/{violation_id}` | Retrieve a violation by ID |

## 13.3 Health Check

**Endpoint:**

```http
GET /health
```

**Example Response:**

```json
{
  "status": "healthy"
}
```

## 13.4 Create a Violation Record

**Endpoint:**

```http
POST /api/v1/violations
```

**Example Request:**

```json
{
  "track_id": 101,
  "plate_number": "ABC123",
  "speed_kmh": 85.5,
  "speed_limit_kmh": 60.0,
  "video_source": "traffic_video.mp4"
}
```

The request schema validates the required tracking and speed fields, along with optional plate, timestamp, and video-source information.

A successful request returns the created violation record.

## 13.5 Retrieve Violation Records

**Endpoint:**

```http
GET /api/v1/violations
```

Optional query parameters:

| Parameter | Description |
|---|---|
| limit | Maximum number of records to return |
| offset | Number of records to skip |

**Example:**

```http
GET /api/v1/violations?limit=10&offset=0
```

**Example Response:**

```json
{
  "items": [],
  "total": 0,
  "limit": 10,
  "offset": 0
}
```

The response includes the returned records, total record count, page size, and pagination offset.

## 13.6 Retrieve a Violation by ID

**Endpoint:**

```http
GET /api/v1/violations/{violation_id}
```

**Example:**

```http
GET /api/v1/violations/1
```

The endpoint returns the matching violation record or an HTTP 404 response when the requested record does not exist.

## 13.7 Interactive API Documentation

FastAPI automatically provides interactive API documentation.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

OpenAPI schema:

```text
http://127.0.0.1:8000/openapi.json
```

---

# 14. Database Design

The project uses SQLAlchemy as its ORM and SQLite as its default relational database.

## 14.1 Database Model

**File:** `app/models/vehicle_violation.py`

The application defines a `VehicleViolation` model.

**Database table:**

```text
vehicle_violations
```

## 14.2 Table Fields

| Field | Description |
|---|---|
| id | Primary key |
| track_id | Vehicle tracking identifier |
| plate_number | Recognized number plate text; nullable |
| speed_kmh | Calculated vehicle speed |
| speed_limit_kmh | Configured speed limit |
| violation_time | Timestamp associated with the violation record |
| video_source | Optional source video information |

## 14.3 Database Components

| Component | File | Responsibility |
|---|---|---|
| Base | `app/db/base.py` | SQLAlchemy declarative base |
| Session | `app/db/session.py` | Engine and database session management |
| Initialization | `app/db/init_db.py` | Database table creation |
| Model | `app/models/vehicle_violation.py` | Violation table definition |
| Repository | `app/repositories/violation_repository.py` | Database access operations |

## 14.4 Repository Operations

The violation repository provides operations for:

- Creating a violation record.
- Retrieving a record by its ID.
- Retrieving multiple records.
- Counting stored records.

The service layer uses these repository operations to implement application-level violation management.

---

# 15. Running the Application

After completing installation and database initialization, start the FastAPI application.

## 15.1 Start the Development Server

```bash
uvicorn app.main:app --reload
```

The server will be available at:

```text
http://127.0.0.1:8000
```

## 15.2 Verify Application Health

Open:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "healthy"
}
```

## 15.3 Open API Documentation

Visit:

```text
http://127.0.0.1:8000/docs
```

Use Swagger UI to inspect and test the available API endpoints.

---

# 16. Testing and Code Quality

Automated tests are included to validate the application's main components.

The test suite is divided into unit and integration tests.

## 16.1 Unit Tests

Unit tests cover individual application components, including:

- DetectionAgent.
- TrackingAgent.
- SpeedAgent.
- PlateAgent.
- FrameOrchestrator.
- Violation repository.
- Violation schemas.
- Violation service.
- Violation API router.
- Main application health endpoint.

## 16.2 Integration Tests

Integration tests verify database and API interactions.

The current integration tests cover:

- Violation repository database integration.
- Violation API database integration.

## 16.3 Run All Tests

```bash
pytest tests -v
```

For a compact result:

```bash
pytest tests -q
```

## 16.4 Run Code Quality Checks

```bash
ruff check app tests
```

## 16.5 Compile Python Files

```bash
python -m compileall -q app tests
```

## 16.6 Current Verification Results

The recorded project verification produced:

| Check | Result |
|---|---|
| Unit and Integration Tests | 39 Passed |
| Ruff Linting | All Checks Passed |
| Python Compilation | Successful |
| Database Initialization | Successful |
| API Integration Tests | Passed |

The test run reported one non-failing Starlette/httpx deprecation warning related to the test client dependency. It did not affect the passing test results.

---

# 17. Implementation Status

The following table describes the current implementation status.

| Component | Status |
|---|---|
| Project Structure | Implemented |
| Application Configuration | Implemented |
| Logging and Exceptions | Implemented |
| OpenCV Video Client | Implemented |
| YOLOv8 Detector Client | Implemented |
| DetectionAgent | Implemented |
| ByteTrack TrackingAgent | Implemented |
| SpeedAgent | Implemented |
| PlateAgent | Implemented |
| EasyOCR Client | Implemented |
| Frame Orchestrator | Implemented |
| SQLAlchemy Database Layer | Implemented |
| Vehicle Violation Model | Implemented |
| Violation Repository | Implemented |
| Pydantic Schemas | Implemented |
| Violation Service | Implemented |
| FastAPI Violation Router | Implemented |
| Health Endpoint | Implemented |
| Unit Tests | Implemented |
| Integration Tests | Implemented |
| End-to-End Video Processing API | Not Yet Implemented |
| Video Upload Endpoint | Not Yet Implemented |
| Live Camera Streaming | Not Yet Implemented |
| Automated Annotated Video Generation | Not Yet Implemented |
| Frontend Dashboard | Not Yet Implemented |
| Automatic Frame-to-Database Violation Integration | Not Yet Implemented |

---

# 18. Limitations

The current implementation provides the core computer vision components and violation management backend, but some production-level capabilities remain outside the current scope.

## 18.1 Video Processing Integration

The frame orchestrator processes individual frames, but a complete end-to-end video processing pipeline has not yet been implemented.

## 18.2 Camera Calibration

Speed estimation requires accurate real-world distance calibration and appropriate virtual detection-line positioning.

Incorrect calibration can produce inaccurate speed measurements.

## 18.3 OCR Accuracy

Number plate recognition can be affected by poor lighting, low resolution, motion blur, camera angle, and regional plate variations.

## 18.4 Database Integration

The violation management API and frame-processing components are implemented separately. Automatic creation of database records from orchestrated frame results still requires integration.

## 18.5 User Interface

The project currently provides a backend API and does not include a graphical dashboard.

## 18.6 Deployment Readiness

Production deployment may require additional configuration for authentication, authorization, monitoring, logging, database management, and operational security.

---

# 19. Future Enhancements

The architecture provides a foundation for extending the system with additional capabilities.

Potential future improvements include:

1. **End-to-End Video Processing:** Add a service to read video files and process frames sequentially.
2. **Live Camera Integration:** Support RTSP streams and connected traffic cameras.
3. **Automated Violation Recording:** Connect orchestrator outputs directly to the violation service and database.
4. **Annotated Video Generation:** Produce processed videos with vehicle bounding boxes, tracking IDs, speed values, and plate information.
5. **Frontend Dashboard:** Develop a web interface for monitoring vehicles and reviewing violation records.
6. **Advanced Camera Calibration:** Introduce perspective correction and more robust real-world distance estimation.
7. **OCR Improvements:** Improve number plate recognition through image preprocessing and region-specific validation.
8. **Authentication and Authorization:** Add secure access controls for API users.
9. **Reporting and Analytics:** Provide violation statistics, vehicle counts, and speed analysis.
10. **Production Deployment:** Add deployment configuration, monitoring, and operational logging.

---

# License

No license has been specified for this project yet. Add a license file before distributing the software publicly.

---

# Acknowledgements

This project uses open-source technologies and libraries, including:

- [Python](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Ultralytics YOLO](https://docs.ultralytics.com/)
- [ByteTrack](https://github.com/ifzhang/ByteTrack)
- [OpenCV](https://opencv.org/)
- [EasyOCR](https://github.com/JaidedAI/EasyOCR)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [Pytest](https://pytest.org/)
- [Ruff](https://docs.astral.sh/ruff/)

---

**Project:** Traffic Speed & Number Plate Recognition System  
**Category:** Computer Vision / Intelligent Transportation Systems  
**Backend:** FastAPI  
**Detection:** YOLOv8  
**Tracking:** ByteTrack  
**OCR:** EasyOCR  
**Database:** SQLite with SQLAlchemy  
**Language:** Python 3.11+
