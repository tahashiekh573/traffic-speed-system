from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.vehicle_violation import VehicleViolation  # noqa: F401
from app.repositories.violation_repository import ViolationRepository


def test_violation_repository_database_integration():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    try:
        with TestingSessionLocal() as session:
            repository = ViolationRepository(session)

            violation = repository.create(
                track_id=101,
                plate_number="ABC123",
                speed_kmh=85.5,
                speed_limit_kmh=60.0,
                video_source="integration_test.mp4",
            )

            session.commit()
            session.refresh(violation)

            saved_violation = repository.get_by_id(violation.id)
            all_violations = repository.get_all(limit=10, offset=0)

            assert saved_violation is not None
            assert saved_violation.track_id == 101
            assert saved_violation.plate_number == "ABC123"
            assert saved_violation.speed_kmh == 85.5
            assert len(all_violations) == 1
            assert repository.count() == 1

    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()



def test_init_db_upgrades_old_table_without_violation_type(tmp_path):
    """Databases created before helmet checks are rebuilt, keeping rows."""
    from sqlalchemy import create_engine, inspect, text

    from app.db.init_db import init_db

    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE vehicle_violations (id INTEGER PRIMARY KEY, "
                "track_id INTEGER NOT NULL, plate_number VARCHAR(20), "
                "speed_kmh FLOAT NOT NULL, speed_limit_kmh FLOAT NOT NULL, "
                "violation_time DATETIME NOT NULL, video_source VARCHAR(255))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO vehicle_violations VALUES "
                "(1, 7, 'ABC123', 85.0, 60.0, '2026-10-30 12:00:00', 'a.mp4')"
            )
        )

    init_db(engine)

    columns = {c["name"]: c for c in inspect(engine).get_columns("vehicle_violations")}
    assert "violation_type" in columns
    assert columns["speed_kmh"]["nullable"] is True

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT track_id, violation_type, speed_kmh FROM vehicle_violations")
        ).one()
    assert tuple(row) == (7, "overspeed", 85.0)

    init_db(engine)  # running again is a no-op
    engine.dispose()


def test_init_db_finishes_a_half_done_upgrade(tmp_path):
    """A leftover *_old table (interrupted upgrade) is merged and removed."""
    from sqlalchemy import create_engine, inspect, text

    from app.db.init_db import init_db

    engine = create_engine(f"sqlite:///{(tmp_path / 'half.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE vehicle_violations_old (id INTEGER PRIMARY KEY, "
                "track_id INTEGER NOT NULL, plate_number VARCHAR(20), "
                "speed_kmh FLOAT NOT NULL, speed_limit_kmh FLOAT NOT NULL, "
                "violation_time DATETIME NOT NULL, video_source VARCHAR(255))"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX ix_vehicle_violations_track_id "
                "ON vehicle_violations_old (track_id)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO vehicle_violations_old VALUES "
                "(3, 9, NULL, 70.0, 60.0, '2026-10-30 12:00:00', 'b.mp4')"
            )
        )
        # The new table exists, but its indexes clashed with the old ones.
        connection.execute(
            text(
                "CREATE TABLE vehicle_violations (id INTEGER PRIMARY KEY, "
                "track_id INTEGER NOT NULL, plate_number VARCHAR(20), "
                "violation_type VARCHAR(20) NOT NULL DEFAULT 'overspeed', "
                "speed_kmh FLOAT, speed_limit_kmh FLOAT NOT NULL, "
                "violation_time DATETIME NOT NULL, video_source VARCHAR(255))"
            )
        )

    init_db(engine)

    inspector = inspect(engine)
    assert "vehicle_violations_old" not in inspector.get_table_names()
    index_names = {i["name"] for i in inspector.get_indexes("vehicle_violations")}
    assert "ix_vehicle_violations_track_id" in index_names
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, violation_type FROM vehicle_violations")
        ).all()
    assert [tuple(r) for r in rows] == [(3, "overspeed")]
    engine.dispose()
