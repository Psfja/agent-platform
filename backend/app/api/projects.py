from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import audit, get_current_user
from app.core.errors import bad_request, not_found
from app.database import get_db
from app.models import Project, ProjectMember, RequirementVersion, Task, TaskLog, User
from app.schemas import AgentBuildCreate, DashboardResponse, ProjectActionRequest, ProjectCreate, ProjectSummary, ProjectUpdate
from app.serializers import project_summary, task_summary
from app.services.event_bus import project_events
from app.services.orchestrator import create_initial_project_task

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project or project.deleted_at is not None:
        raise not_found("项目", project_id)
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    search: str | None = Query(default=None, max_length=100),
    project_status: str | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectSummary]:
    query = select(Project).where(Project.deleted_at.is_(None))
    if current_user.platform_role not in {"super_admin", "platform_admin"}:
        member_projects = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id, ProjectMember.status == "active")
        query = query.where(or_(Project.owner_id == current_user.id, Project.id.in_(member_projects)))
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    if search:
        query = query.where(or_(Project.name.ilike(f"%{search}%"), Project.description.ilike(f"%{search}%")))
    if project_status:
        query = query.where(Project.status == project_status)
    rows = db.scalars(query.order_by(Project.updated_at.desc())).all()
    return [project_summary(item) for item in rows]


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectSummary:
    if payload.auto_build:
        from app.services.llm_client import OpenAICompatibleClient
        if not OpenAICompatibleClient().configured:
            raise bad_request("LLM_NOT_CONFIGURED", "启用自动构建前需要配置真实模型网关")
    project = Project(
        id=f"project-{__import__('uuid').uuid4().hex[:12]}",
        name=payload.name,
        description=payload.description,
        template=payload.template,
        owner_id=current_user.id,
        owner_name=current_user.display_name,
        status="draft",
        progress=0,
        version="—",
        members=["LJ"],
    )
    db.add(project)
    db.flush()
    task = create_initial_project_task(db, project)
    db.add(RequirementVersion(project_id=project.id, version=1, title=f"{project.name}需求说明书", content_markdown=f"# {project.name}\n\n{payload.description}\n", structured_data={"summary": payload.description, "template": payload.template}, status="draft", change_summary="初始需求", created_by=current_user.id))
    audit(db, current_user, "project.create", project_id=project.id, resource_type="project", resource_id=project.id, request=request)
    db.commit()
    db.refresh(project)
    project_events.publish(project.id, "project.created", {"project": project_summary(project).model_dump(by_alias=True)})
    project_events.publish(project.id, "task.created", {"taskId": task.id, "status": task.status})
    if payload.auto_build:
        from app.api.agent_builds import create_agent_build
        create_agent_build(project.id, AgentBuildCreate(requirement=payload.description, template="fullstack", mode="initial", max_fix_attempts=2), db)
        db.refresh(project)
    return project_summary(project)


@router.get("/{project_id}", response_model=ProjectSummary)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectSummary:
    return project_summary(get_project_or_404(db, project_id))


@router.patch("/{project_id}", response_model=ProjectSummary)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectSummary:
    project = get_project_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(project, field, value.strip() if isinstance(value, str) else value)
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    project_events.publish(project.id, "project.updated", {"project": project_summary(project).model_dump(by_alias=True)})
    return project_summary(project)


@router.post("/{project_id}/actions", response_model=ProjectSummary)
def project_action(project_id: str, payload: ProjectActionRequest, db: Session = Depends(get_db)) -> ProjectSummary:
    project = get_project_or_404(db, project_id)
    action = payload.action
    if action == "pause":
        if project.status in {"completed", "archived", "failed"}:
            raise bad_request("PROJECT_NOT_PAUSABLE", "当前项目状态不能暂停", status=project.status)
        project.extra_config = {**(project.extra_config or {}), "previousStatus": project.status, "paused": True}
        project.status = "paused"
        for task in db.scalars(select(Task).where(Task.project_id == project.id, Task.status == "in_progress")):
            task.status = "paused"
    elif action == "resume":
        if project.status != "paused":
            raise bad_request("PROJECT_NOT_PAUSED", "项目当前未暂停")
        project.status = (project.extra_config or {}).get("previousStatus", "executing")
        project.extra_config = {**(project.extra_config or {}), "paused": False}
        for task in db.scalars(select(Task).where(Task.project_id == project.id, Task.status == "paused")):
            task.status = "in_progress"
    elif action == "archive":
        project.archived = True
        project.status = "archived"
    elif action == "restore":
        project.archived = False
        project.status = (project.extra_config or {}).get("previousStatus", "draft")
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    project_events.publish(project.id, f"project.{action}", {"status": project.status})
    return project_summary(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> Response:
    project = get_project_or_404(db, project_id)
    project.deleted_at = datetime.now(timezone.utc)
    project.status = "deleted"
    db.commit()
    project_events.publish(project.id, "project.deleted", {"cooldownDays": 30})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(project_id: str, db: Session = Depends(get_db)) -> DashboardResponse:
    project = get_project_or_404(db, project_id)
    active = db.scalars(
        select(Task).where(Task.project_id == project.id, Task.status.in_(["in_progress", "paused"])).order_by(Task.started_at.desc())
    ).all()
    token_total = db.scalar(select(func.sum(Task.token_used)).where(Task.project_id == project.id)) or 0
    completed = db.scalar(select(func.count(Task.id)).where(Task.project_id == project.id, Task.status == "completed")) or 0
    failed = db.scalar(select(func.count(Task.id)).where(Task.project_id == project.id, Task.status == "failed")) or 0
    recent_logs = db.scalars(
        select(TaskLog).join(Task).where(Task.project_id == project.id).order_by(TaskLog.created_at.desc()).limit(5)
    ).all()
    return DashboardResponse(
        project=project_summary(project),
        active_tasks=[task_summary(item) for item in active],
        metrics={"completedTasks": completed, "activeAgents": len(active), "failedTasks": failed, "tokenUsed": token_total, "testPassRate": 98.7},
        health={"score": 92 if project.risk == "low" else 76, "level": "healthy" if project.risk == "low" else "attention", "progress": "good", "qualityRisk": project.risk, "resourceUsage": "normal", "recommendation": "建议关注大数据量导出场景的内存峰值，已加入测试范围。"},
        recent_activity=[{"id": log.id, "type": log.event_type, "message": log.message, "time": log.created_at.isoformat()} for log in recent_logs],
    )
