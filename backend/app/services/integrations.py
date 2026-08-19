from __future__ import annotations

import hashlib
import json
import mimetypes
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path

import httpx
from minio import Minio
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, Project, User


class ArtifactStorage:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.minio_endpoint and self.settings.minio_access_key and self.settings.minio_secret_key)

    def upload(self, path: Path, object_name: str) -> dict:
        if not self.configured:
            return {"provider": "local", "path": str(path), "size": path.stat().st_size, "checksum": self._checksum(path)}
        client = Minio(self.settings.minio_endpoint, access_key=self.settings.minio_access_key, secret_key=self.settings.minio_secret_key, secure=self.settings.minio_secure)
        if not client.bucket_exists(self.settings.minio_bucket): client.make_bucket(self.settings.minio_bucket)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        client.fput_object(self.settings.minio_bucket, object_name, str(path), content_type=content_type)
        return {"provider": "minio", "bucket": self.settings.minio_bucket, "object": object_name, "uri": f"s3://{self.settings.minio_bucket}/{object_name}", "size": path.stat().st_size, "checksum": self._checksum(path)}

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
        return digest.hexdigest()


class GitPublisher:
    def __init__(self) -> None: self.settings = get_settings()

    def publish(self, workspace: Path, branch: str, message: str, remote_url: str | None = None) -> dict:
        def run(*args):
            result = subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, timeout=120, check=False)
            if result.returncode: raise RuntimeError(result.stderr[-2000:])
            return result.stdout.strip()
        if not (workspace / ".git").exists(): run("init")
        run("config", "user.name", "Agent Platform")
        run("config", "user.email", "agent-platform@local")
        run("checkout", "-B", branch)
        run("add", "backend", "frontend", "docs")
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workspace).returncode != 0
        if staged: run("commit", "-m", message)
        commit = run("rev-parse", "HEAD") if staged or (workspace / ".git").exists() else ""
        remote = remote_url or self.settings.git_remote_url
        pushed = False
        if remote:
            existing = subprocess.run(["git", "remote", "get-url", "origin"], cwd=workspace, capture_output=True).returncode == 0
            run("remote", "set-url" if existing else "add", "origin", remote)
            run("push", "-u", "origin", branch); pushed = True
        return {"commit": commit, "branch": branch, "remote": remote, "pushed": pushed}


class NotificationService:
    def __init__(self) -> None: self.settings = get_settings()

    def notify(self, db: Session, project: Project, event_type: str, title: str, content: str) -> list[Notification]:
        owner = db.get(User, project.owner_id)
        rows = [Notification(user_id=project.owner_id, project_id=project.id, channel="in_app", event_type=event_type, title=title, content=content, status="sent")]
        if owner and self.settings.smtp_host:
            row = Notification(user_id=owner.id, project_id=project.id, channel="email", event_type=event_type, title=title, content=content, status="pending")
            try:
                message = EmailMessage(); message["Subject"] = title; message["From"] = self.settings.smtp_username; message["To"] = owner.email; message.set_content(content)
                with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
                    client.starttls()
                    if self.settings.smtp_username: client.login(self.settings.smtp_username, self.settings.smtp_password)
                    client.send_message(message)
                row.status = "sent"
            except Exception as exc: row.status = "failed"; row.error_message = str(exc)
            rows.append(row)
        if self.settings.notification_webhook_url:
            row = Notification(user_id=project.owner_id, project_id=project.id, channel="webhook", event_type=event_type, title=title, content=content, status="pending")
            try:
                response = httpx.post(self.settings.notification_webhook_url, json={"event": event_type, "title": title, "content": content, "projectId": project.id}, timeout=10); response.raise_for_status(); row.status = "sent"
            except Exception as exc: row.status = "failed"; row.error_message = str(exc)
            rows.append(row)
        db.add_all(rows); return rows


artifact_storage = ArtifactStorage()
git_publisher = GitPublisher()
notification_service = NotificationService()
