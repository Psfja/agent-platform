from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_platform_admin
from app.database import get_db
from app.models import AgentBuild, ApplicationDeployment, Notification, Project, QueuedJob, SandboxRun, Task, User
from app.services.integrations import artifact_storage
from app.services.task_queue import persistent_queue

router = APIRouter(tags=["operations"])


@router.get("/monitoring/summary", dependencies=[Depends(require_platform_admin)])
def monitoring_summary(db: Session = Depends(get_db)) -> dict:
    return {
        "system": {"cpuPercent": psutil.cpu_percent(interval=0.05), "memoryPercent": psutil.virtual_memory().percent, "diskPercent": psutil.disk_usage('/').percent, "loadAverage": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else []},
        "projects": {"total": db.scalar(select(func.count(Project.id))) or 0, "active": db.scalar(select(func.count(Project.id)).where(Project.status.in_(["planning", "executing", "testing", "deploying"]))) or 0},
        "tasks": {"running": db.scalar(select(func.count(Task.id)).where(Task.status == "in_progress")) or 0, "failed": db.scalar(select(func.count(Task.id)).where(Task.status == "failed")) or 0},
        "agentBuilds": {"completed": db.scalar(select(func.count(AgentBuild.id)).where(AgentBuild.status == "completed")) or 0, "failed": db.scalar(select(func.count(AgentBuild.id)).where(AgentBuild.status == "failed")) or 0, "tokens": db.scalar(select(func.sum(AgentBuild.prompt_tokens + AgentBuild.completion_tokens))) or 0},
        "deployments": {"running": db.scalar(select(func.count(ApplicationDeployment.id)).where(ApplicationDeployment.status == "running")) or 0, "failed": db.scalar(select(func.count(ApplicationDeployment.id)).where(ApplicationDeployment.status == "failed")) or 0},
        "queue": persistent_queue.status(),
        "storage": {"provider": "minio" if artifact_storage.configured else "local", "configured": artifact_storage.configured},
    }


@router.get("/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app").order_by(Notification.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "eventType": row.event_type, "title": row.title, "content": row.content, "status": row.status, "readAt": row.read_at, "createdAt": row.created_at} for row in rows]


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if row:
        row.read_at = datetime.now(timezone.utc); db.commit()
    return {"ok": bool(row)}


@router.get("/integrations/status", dependencies=[Depends(require_platform_admin)])
def integrations_status() -> dict:
    from app.core.config import get_settings
    settings = get_settings()
    return {"git": {"configured": bool(settings.git_remote_url), "remote": settings.git_remote_url}, "minio": {"configured": artifact_storage.configured, "endpoint": settings.minio_endpoint, "bucket": settings.minio_bucket}, "smtp": {"configured": bool(settings.smtp_host), "host": settings.smtp_host}, "webhook": {"configured": bool(settings.notification_webhook_url)}}
