"""Database engine and session management."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PROJECT_ROOT, get_settings

SQLITE_PREFIX = "sqlite"


def resolve_database_url(database_url: str) -> str:
    """Anchor relative SQLite files to the project root and create the folder."""
    url = make_url(database_url)

    if not url.drivername.startswith(SQLITE_PREFIX):
        return database_url

    database = url.database
    if not database or database == ":memory:":
        return database_url

    path = Path(database)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()

    path.parent.mkdir(parents=True, exist_ok=True)
    query = f"?{database_url.split('?', 1)[1]}" if "?" in database_url else ""
    return f"{url.drivername}:///{path.as_posix()}{query}"


settings = get_settings()
database_url = resolve_database_url(settings.database_url)

connect_args = (
    {"check_same_thread": False}
    if database_url.startswith(SQLITE_PREFIX)
    else {}
)

engine = create_engine(database_url, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Iterator[Session]:
    """Provide a database session and close it after use."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
