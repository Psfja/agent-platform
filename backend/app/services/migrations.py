from pathlib import Path
import hashlib
import sqlite3
import subprocess
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.database import engine


def _config() -> Config:
    settings = get_settings()
    config = Config(str(settings.base_dir / "alembic.ini"))
    config.set_main_option("script_location", str(settings.base_dir / "app" / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return config


def run_platform_migrations() -> None:
    command.upgrade(_config(), "head")


def migration_status() -> dict:
    config = _config()
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return {"currentRevision": current, "headRevision": head, "upToDate": current == head, "enabled": get_settings().run_db_migrations}


def create_database_backup() -> dict:
    settings = get_settings(); backup_dir = settings.base_dir / "data" / "backups"; backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if settings.is_sqlite:
        target = backup_dir / f"agent-platform-{stamp}.sqlite3"
        source_path = Path(settings.database_url.removeprefix("sqlite:///"))
        source = sqlite3.connect(source_path); destination = sqlite3.connect(target)
        try: source.backup(destination)
        finally: destination.close(); source.close()
        database_type = "sqlite"
    else:
        target = backup_dir / f"agent-platform-{stamp}.dump"
        result = subprocess.run(["pg_dump", "--format=custom", "--file", str(target), settings.database_url.replace("postgresql+psycopg", "postgresql")], capture_output=True, text=True, timeout=300)
        if result.returncode: raise RuntimeError(result.stderr[-2000:])
        database_type = "postgresql"
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {"databaseType": database_type, "filePath": str(target), "sizeBytes": target.stat().st_size, "checksum": digest, "revision": migration_status()["currentRevision"]}


def downgrade_database(revision: str) -> None:
    command.downgrade(_config(), revision)
