import logging
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)


def backup_sqlite_before_upgrade(
    database_url: str,
    configuration: Config,
) -> Path | None:
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "sqlite" or not parsed_url.database:
        return None
    database_path = Path(parsed_url.database).expanduser().resolve()
    if not database_path.is_file() or database_path.stat().st_size == 0:
        return None

    current_revision: str | None = None
    with sqlite3.connect(database_path) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        if table_exists:
            row = connection.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
            current_revision = str(row[0]) if row else None

    target_revision = ScriptDirectory.from_config(configuration).get_current_head()
    if current_revision == target_revision:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = database_path.with_name(f"{database_path.name}.backup-{timestamp}")
    shutil.copy2(database_path, backup_path)
    logger.info("Created database backup before migration: %s", backup_path.name)
    return backup_path


def upgrade_database(database_url: str, assets_root: Path) -> None:
    configuration = Config(str(assets_root / "alembic.ini"))
    configuration.attributes["configure_logger"] = False
    configuration.set_main_option("script_location", str(assets_root / "migrations"))
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    backup_sqlite_before_upgrade(database_url, configuration)
    command.upgrade(configuration, "head")
