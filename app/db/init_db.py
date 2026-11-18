"""Create tables and apply small in-place schema upgrades."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import engine
from app.models import vehicle_violation  # noqa: F401

logger = get_logger(__name__)

VIOLATIONS_TABLE = "vehicle_violations"
OLD_TABLE = f"{VIOLATIONS_TABLE}_old"
COPY_COLUMNS = (
    "id, track_id, plate_number, speed_kmh, speed_limit_kmh, "
    "violation_time, video_source"
)


def _upgrade_violations_table(bind: Engine) -> None:
    """Add ``violation_type`` and make ``speed_kmh`` nullable on old databases.

    SQLite cannot change a column's nullability, so the old table is
    renamed, a new one is created and the rows are copied over as
    overspeed violations. Every step is idempotent: if an earlier upgrade
    stopped half-way (a ``*_old`` table is left), it is completed here.
    """
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if VIOLATIONS_TABLE in tables:
        columns = {c["name"] for c in inspector.get_columns(VIOLATIONS_TABLE)}
        if "violation_type" not in columns:
            if OLD_TABLE in tables:
                raise RuntimeError(
                    f"Both {VIOLATIONS_TABLE} (old schema) and {OLD_TABLE} exist; "
                    "resolve manually."
                )
            logger.info("Upgrading %s with a violation_type column", VIOLATIONS_TABLE)
            with bind.begin() as connection:
                connection.execute(
                    text(f"ALTER TABLE {VIOLATIONS_TABLE} RENAME TO {OLD_TABLE}")
                )
            tables = set(inspect(bind).get_table_names())

    if OLD_TABLE not in tables:
        return

    table = Base.metadata.tables[VIOLATIONS_TABLE]

    # Index names stay attached to the renamed table and would clash.
    with bind.begin() as connection:
        for index in inspect(bind).get_indexes(OLD_TABLE):
            connection.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))

    table.create(bind=bind, checkfirst=True)
    for index in table.indexes:
        index.create(bind=bind, checkfirst=True)

    with bind.begin() as connection:
        connection.execute(
            text(
                f"INSERT OR IGNORE INTO {VIOLATIONS_TABLE} "
                f"({COPY_COLUMNS}, violation_type) "
                f"SELECT {COPY_COLUMNS}, 'overspeed' FROM {OLD_TABLE}"
            )
        )
        connection.execute(text(f"DROP TABLE {OLD_TABLE}"))

    logger.info("Upgrade of %s completed", VIOLATIONS_TABLE)


def init_db(bind: Engine | None = None) -> None:
    """Create all registered database tables and upgrade old ones."""
    bind = bind or engine
    _upgrade_violations_table(bind)
    Base.metadata.create_all(bind=bind)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
