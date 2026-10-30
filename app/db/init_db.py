from app.db.base import Base
from app.db.session import engine
from app.models import vehicle_violation  # noqa: F401


def init_db() -> None:
    """Create all registered database tables."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
