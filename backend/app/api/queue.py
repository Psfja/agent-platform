from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_platform_admin
from app.database import get_db
from app.models import DatabaseBackup, QueuedJob, User
from app.services.migrations import create_database_backup, downgrade_database, migration_status
from app.services.task_queue import persistent_queue

router = APIRouter(prefix="/queue", tags=["durable-task-queue"], dependencies=[Depends(require_platform_admin)])


@router.get("/status")
def queue_status() -> dict:
    return persistent_queue.status()


@router.get("/migrations")
def database_migration_status() -> dict:
    return migration_status()


@router.post("/database/backups")
def backup_database(user: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    result = create_database_backup()
    item = DatabaseBackup(database_type=result["databaseType"], revision=result["revision"], file_path=result["filePath"], size_bytes=result["sizeBytes"], checksum=result["checksum"], created_by=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, **result, "createdAt": item.created_at}


@router.get("/database/backups")
def list_database_backups(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(DatabaseBackup).order_by(DatabaseBackup.created_at.desc()).limit(100)).all()
    return [{"id": item.id, "databaseType": item.database_type, "revision": item.revision, "filePath": item.file_path, "sizeBytes": item.size_bytes, "checksum": item.checksum, "status": item.status, "createdAt": item.created_at} for item in rows]


@router.post("/database/downgrade")
def downgrade_platform_database(payload: dict, user: User = Depends(require_platform_admin)) -> dict:
    revision = str(payload.get("revision", ""))
    if not revision or payload.get("confirmation") != "DOWNGRADE":
        from app.core.errors import AppError
        raise AppError(400, "DOWNGRADE_CONFIRMATION_REQUIRED", "数据库降级需要 confirmation=DOWNGRADE")
    backup = create_database_backup(); downgrade_database(revision)
    return {"status": "completed", "targetRevision": revision, "backup": backup, "migration": migration_status()}


@router.get("/jobs")
def queue_jobs(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    jobs = db.scalars(select(QueuedJob).order_by(QueuedJob.created_at.desc()).limit(limit)).all()
    return [{"id": job.id, "jobType": job.job_type, "status": job.status, "attempts": job.attempts, "maxAttempts": job.max_attempts, "workerId": job.worker_id, "errorMessage": job.error_message, "createdAt": job.created_at, "startedAt": job.started_at, "finishedAt": job.finished_at} for job in jobs]
