import logging
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.migrations import upgrade_database


def test_startup_applies_alembic_migration(
    client: TestClient,
    test_settings: Settings,
) -> None:
    database_path = Path(test_settings.database_url.removeprefix("sqlite:///"))

    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert version == ("20260809_02",)


def test_legacy_sqlite_is_backed_up_before_migration(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO legacy_marker VALUES ('keep me')")

    upgrade_database(
        f"sqlite:///{database_path}",
        Path(__file__).resolve().parent.parent,
    )

    backups = list(tmp_path.glob("legacy.db.backup-*"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        marker = connection.execute("SELECT value FROM legacy_marker").fetchone()
    assert marker == ("keep me",)


def test_programmatic_migration_preserves_application_logging(tmp_path: Path) -> None:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    application_handler = logging.FileHandler(tmp_path / "application.log")
    root_logger.handlers = [application_handler]
    try:
        upgrade_database(
            f"sqlite:///{tmp_path / 'logging.db'}",
            Path(__file__).resolve().parent.parent,
        )

        assert root_logger.handlers == [application_handler]
    finally:
        application_handler.close()
        root_logger.handlers = original_handlers
