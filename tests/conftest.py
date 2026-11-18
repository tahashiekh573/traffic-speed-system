"""Test-wide settings, applied before the application is imported.

- Never load the real vision models during tests.
- Never touch the real database (data/traffic.db): the app's startup
  runs ``init_db`` whenever a test starts a ``TestClient``.
"""

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="traffic-tests-")) / "test.db"

os.environ.setdefault("PRELOAD_MODELS", "false")
os.environ["HELMET_DETECTION_ENABLED"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
