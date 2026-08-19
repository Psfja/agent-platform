from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg

from app.core.config import get_settings


class GeneratedDatabaseManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.generated_database_backup_dir.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return self.settings.generated_database_url.startswith(("postgresql://", "postgresql+psycopg://"))

    def schema_name(self, project_id: str) -> str:
        return "app_" + re.sub(r"[^a-z0-9_]", "_", project_id.lower())[:48]

    def prepare_and_migrate(self, project_id: str, deployment_id: str, backend_dir: Path) -> dict:
        if not self.configured:
            return {"configured": False, "mode": "application-managed"}
        schema = self.schema_name(project_id)
        base_url = self.settings.generated_database_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(base_url, autocommit=True) as connection:
            connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        backup = self.backup(project_id, deployment_id, schema)
        app_url = self._schema_url(base_url, schema)
        alembic_ini = backend_dir / "alembic.ini"
        if alembic_ini.is_file():
            env = {**os.environ, "DATABASE_URL": app_url}
            result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend_dir, env=env, capture_output=True, text=True, timeout=300)
            if result.returncode:
                self.restore(backup["filePath"])
                raise RuntimeError(f"Generated application migration failed: {result.stderr[-3000:]}")
        return {"configured": True, "schema": schema, "databaseUrl": app_url, "backup": backup, "migrationApplied": alembic_ini.is_file()}

    def backup(self, project_id: str, deployment_id: str, schema: str) -> dict:
        if not shutil.which("pg_dump"):
            raise RuntimeError("pg_dump is required for generated database backup")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.settings.generated_database_backup_dir / f"{project_id}-{deployment_id[-8:]}-{stamp}.dump"
        url = self.settings.generated_database_url.replace("postgresql+psycopg://", "postgresql://")
        result = subprocess.run(["pg_dump", "--format=custom", "--schema", schema, "--file", str(target), url], capture_output=True, text=True, timeout=300)
        if result.returncode: raise RuntimeError(result.stderr[-3000:])
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return {"filePath": str(target), "schema": schema, "sizeBytes": target.stat().st_size, "checksum": digest}

    def restore(self, backup_path: str) -> None:
        if not shutil.which("pg_restore"): raise RuntimeError("pg_restore is required for generated database rollback")
        path = Path(backup_path)
        if not path.is_file() or self.settings.generated_database_backup_dir not in path.resolve().parents: raise RuntimeError("invalid generated database backup path")
        url = self.settings.generated_database_url.replace("postgresql+psycopg://", "postgresql://")
        result = subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", url, str(path)], capture_output=True, text=True, timeout=600)
        if result.returncode: raise RuntimeError(result.stderr[-3000:])

    @staticmethod
    def _schema_url(url: str, schema: str) -> str:
        parts = urlsplit(url); query = dict(parse_qsl(parts.query)); query["options"] = f"-csearch_path={schema},public"
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


generated_database_manager = GeneratedDatabaseManager()
