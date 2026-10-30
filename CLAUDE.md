# Traffic Speed + Number Plate System

## 1. Project Overview

Build a computer vision based traffic monitoring system
using YOLOv8, ByteTrack, OpenCV and EasyOCR.

The system must detect vehicles, track them, calculate
their speeds and recognize number plates of overspeeding
vehicles.

This is NOT an LLM-based project.

## 2. Architecture

Follow layered architecture:

- core/: Configuration, dependencies, logging and exceptions.
- middlewares/: Request ID, logging and error handling.
- routers/: FastAPI endpoints.
- schemas/: Request and response validation.
- services/: Business logic.
- orchestrators/: Coordinate the complete frame pipeline.
- agents/: Independent computer vision tasks.
- clients/: External library wrappers.
- repositories/: Database and file persistence.
- models/: SQLAlchemy database entities.
- db/: Database session management.

## 3. Computer Vision Components

Use these independent agents:

1. DetectionAgent: Detect vehicles using YOLOv8.
2. TrackingAgent: Track vehicles using ByteTrack.
3. SpeedAgent: Calculate vehicle speed in km/h.
4. PlateAgent: Recognize number plates using EasyOCR.

## 4. Important Rules

- Agents must have one responsibility each.
- Agents must not directly call other agents.
- Agents must not save files or database records.
- Agents must return structured data.
- Orchestrator coordinates all agents.
- Clients wrap external libraries.
- Services contain application business logic.
- Repositories handle persistence.
- Routers handle HTTP requests only.
- Configuration must come from environment variables.
- Never hardcode configurable values.
- Use dependency injection.
- Write unit tests for individual components.
- Use type hints and meaningful docstrings.
- Follow PEP 8 and Ruff conventions.
- Handle errors explicitly.
- Do not introduce unnecessary dependencies.

## 5. Project Structure

Follow the directory structure already created
in this repository.

Every Python package directory must contain
an __init__.py file.

## 6. No LLM / Prompts Folder

This project uses computer vision, not an LLM.

Therefore, do not create a prompts/ directory.
Do not add prompt templates or LLM integrations.

## 7. Development Workflow

Build the project incrementally in the following order:

1. Setup and project structure.
2. Core configuration, logging and exceptions.
3. Video and YOLO clients.
4. DetectionAgent.
5. TrackingAgent.
6. SpeedAgent.
7. PlateAgent and OCR client.
8. Traffic pipeline orchestrator.
9. Database models and repositories.
10. Services and FastAPI routers.
11. Unit and integration tests.
12. README and demonstration.

## 8. Strict Development Instructions

- Only implement the step explicitly requested.
- Do not implement future steps without approval.
- Do not modify unrelated files.
- Do not delete existing working functionality.
- Test each completed step.
- Explain files created and changes made.
- Stop after completing the requested step.
- Wait for explicit approval before continuing.
