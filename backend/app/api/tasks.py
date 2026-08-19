from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.core.errors import bad_request, conflict, not_found
from app.database import get_db
from app.models import Intervention, Task, TaskLog
from app.schemas import InterventionCreate, InterventionResponse, LogResponse, TaskActionRequest, TaskSummary
from app.serializers import intervention_response, log_response, task_summary
from app.services.event_bus import project_events


router = APIRouter(tags=["tasks"])


def get_task_or_404(db: Session, project_id: str, task_id: str) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    if not task:
        raise not_found("任务", task_id)
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[TaskSummary])
def list_tasks(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    task_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[TaskSummary]:
    get_project_or_404(db, project_id)
    query = select(Task).where(Task.project_id == project_id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if task_type:
        query = query.where(Task.task_type == task_type)
    rows = db.scalars(query.order_by(Task.created_at.asc())).all()
    return [task_summary(item) for item in rows]


@router.get("/projects/{project_id}/tasks/{task_id}", response_model=TaskSummary)
def get_task(project_id: str, task_id: str, db: Session = Depends(get_db)) -> TaskSummary:
    return task_summary(get_task_or_404(db, project_id, task_id))


@router.post("/projects/{project_id}/tasks/{task_id}/actions", response_model=TaskSummary)
def task_action(project_id: str, task_id: str, payload: TaskActionRequest, db: Session = Depends(get_db)) -> TaskSummary:
    project = get_project_or_404(db, project_id)
    task = get_task_or_404(db, project_id, task_id)
    action = payload.action
    if action == "pause":
        if task.status != "in_progress":
            raise bad_request("TASK_NOT_RUNNING", "仅执行中的任务可以暂停", status=task.status)
        task.status = "paused"
        message = "任务已在安全点暂停。"
    elif action == "resume":
        if task.status != "paused":
            raise bad_request("TASK_NOT_PAUSED", "仅已暂停的任务可以继续", status=task.status)
        task.status = "in_progress"
        message = "任务已恢复执行。"
    elif action == "cancel":
        if task.status in {"completed", "cancelled"}:
            raise conflict("TASK_ALREADY_FINISHED", "任务已结束，不能终止", status=task.status)
        task.status = "cancelled"
        task.finished_at = datetime.now(timezone.utc)
        message = "任务已终止。"
    else:  # retry
        if task.status not in {"failed", "cancelled"}:
            raise bad_request("TASK_NOT_RETRYABLE", "只有失败或已终止任务可以重试", status=task.status)
        task.status = "in_progress"
        task.progress = 0
        task.started_at = datetime.now(timezone.utc)
        task.finished_at = None
        message = "任务已重新进入执行队列。"
    task.updated_at = datetime.now(timezone.utc)
    db.add(TaskLog(task_id=task.id, level="system", event_type="human_action", message=message))
    db.commit()
    db.refresh(task)
    project_events.publish(project_id, "task.status_changed", {"taskId": task.id, "status": task.status, "progress": task.progress})
    return task_summary(task)


@router.get("/projects/{project_id}/tasks/{task_id}/logs", response_model=list[LogResponse])
def list_task_logs(
    project_id: str,
    task_id: str,
    level: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[LogResponse]:
    get_task_or_404(db, project_id, task_id)
    query = select(TaskLog).where(TaskLog.task_id == task_id)
    if level:
        query = query.where(TaskLog.level == level)
    if search:
        query = query.where(TaskLog.message.ilike(f"%{search}%"))
    rows = db.scalars(query.order_by(TaskLog.created_at.asc()).limit(limit)).all()
    return [log_response(item) for item in rows]


@router.post(
    "/projects/{project_id}/tasks/{task_id}/interventions",
    response_model=InterventionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_intervention(project_id: str, task_id: str, payload: InterventionCreate, db: Session = Depends(get_db)) -> InterventionResponse:
    task = get_task_or_404(db, project_id, task_id)
    if task.status in {"completed", "cancelled", "failed"}:
        raise conflict("TASK_ALREADY_FINISHED", "任务已结束，不能发送干预指令", status=task.status)
    queued = db.scalar(select(Intervention).where(Intervention.task_id == task_id, Intervention.status == "queued"))
    item = Intervention(
        project_id=project_id,
        task_id=task_id,
        intervention_type=payload.intervention_type,
        content=payload.content,
        status="queued",
    )
    db.add(item)
    db.flush()
    if queued:
        item.agent_response = "已有指令正在处理，本指令已按时间顺序排队。"
    else:
        item.agent_response = "已接收，将在当前工具调用完成后优先处理。"
    db.add(TaskLog(task_id=task.id, level="info", event_type="human_intervention", message=f"林嘉：{payload.content}", metadata_json={"interventionId": item.id, "type": payload.intervention_type}))
    db.commit()
    db.refresh(item)
    project_events.publish(project_id, "task.intervention_queued", {"taskId": task_id, "interventionId": item.id, "content": item.content})
    return intervention_response(item)


@router.get("/projects/{project_id}/tasks/{task_id}/interventions", response_model=list[InterventionResponse])
def list_interventions(project_id: str, task_id: str, db: Session = Depends(get_db)) -> list[InterventionResponse]:
    get_task_or_404(db, project_id, task_id)
    rows = db.scalars(select(Intervention).where(Intervention.task_id == task_id).order_by(Intervention.created_at.desc())).all()
    return [intervention_response(item) for item in rows]
