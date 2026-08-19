from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.api.tasks import get_task_or_404
from app.core.errors import not_found
from app.database import get_db
from app.models import AgentMemory, SandboxRun, TaskLog
from app.schemas import (
    AgentContextResponse, MemoryCreate, MemoryResponse, MemoryUpdate,
    SandboxExecuteRequest, SandboxRunResponse, SandboxStatusResponse,
    SkillExecuteRequest, SkillManifestResponse,
)
from app.serializers import memory_response, sandbox_run_response
from app.services.agent_runtime import agent_runtime
from app.services.event_bus import project_events
from app.services.memory import memory_service
from app.services.sandbox import sandbox_manager
from app.services.skill_loader import skill_registry

router = APIRouter(tags=["agent-runtime"])


def get_memory_or_404(db: Session, project_id: str, memory_id: str) -> AgentMemory:
    item = db.scalar(select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.project_id == project_id))
    if not item:
        raise not_found("记忆", memory_id)
    return item


@router.get("/projects/{project_id}/memories", response_model=list[MemoryResponse])
def list_memories(
    project_id: str,
    agent_key: str | None = None,
    memory_type: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MemoryResponse]:
    get_project_or_404(db, project_id)
    items = memory_service.retrieve(db, project_id, agent_key, search, memory_type, limit, touch=True)
    db.commit()
    return [memory_response(item) for item in items]


@router.post("/projects/{project_id}/memories", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(project_id: str, payload: MemoryCreate, db: Session = Depends(get_db)) -> MemoryResponse:
    get_project_or_404(db, project_id)
    item = memory_service.create(db, project_id, payload)
    db.commit()
    db.refresh(item)
    project_events.publish(project_id, "agent.memory_created", {"memoryId": item.id, "agentKey": item.agent_key, "type": item.memory_type})
    return memory_response(item)


@router.patch("/projects/{project_id}/memories/{memory_id}", response_model=MemoryResponse)
def update_memory(project_id: str, memory_id: str, payload: MemoryUpdate, db: Session = Depends(get_db)) -> MemoryResponse:
    item = get_memory_or_404(db, project_id, memory_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, "metadata_json" if field == "metadata" else field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return memory_response(item)


@router.delete("/projects/{project_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(project_id: str, memory_id: str, db: Session = Depends(get_db)) -> Response:
    item = get_memory_or_404(db, project_id, memory_id)
    db.delete(item)
    db.commit()
    project_events.publish(project_id, "agent.memory_deleted", {"memoryId": memory_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/skills", response_model=list[SkillManifestResponse])
def list_skills(agent_key: str | None = None) -> list[SkillManifestResponse]:
    return [SkillManifestResponse(**item.to_dict()) for item in skill_registry.list(agent_key)]


@router.post("/skills/reload", response_model=list[SkillManifestResponse])
def reload_skills() -> list[SkillManifestResponse]:
    return [SkillManifestResponse(**item.to_dict()) for item in skill_registry.reload()]


@router.get("/skills/{skill_name}", response_model=SkillManifestResponse)
def get_skill(skill_name: str) -> SkillManifestResponse:
    return SkillManifestResponse(**skill_registry.get(skill_name).to_dict())


@router.get("/sandbox/status", response_model=SandboxStatusResponse)
def sandbox_status() -> SandboxStatusResponse:
    return SandboxStatusResponse(**sandbox_manager.status())


@router.post(
    "/projects/{project_id}/sandbox/runs",
    response_model=SandboxRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_in_sandbox(project_id: str, payload: SandboxExecuteRequest, db: Session = Depends(get_db)) -> SandboxRunResponse:
    get_project_or_404(db, project_id)
    if payload.task_id:
        get_task_or_404(db, project_id, payload.task_id)
    run = sandbox_manager.execute_and_record(
        db, project_id=project_id, code=payload.code, stdin=payload.stdin,
        task_id=payload.task_id, timeout_seconds=payload.timeout_seconds,
    )
    if payload.task_id:
        db.add(TaskLog(
            task_id=payload.task_id,
            level="success" if run.status == "completed" else "error",
            event_type="sandbox_execution",
            message=f"沙箱执行{ '完成' if run.status == 'completed' else '失败' }：{run.id}",
            metadata_json={"sandboxRunId": run.id, "status": run.status, "exitCode": run.exit_code},
        ))
    db.commit()
    db.refresh(run)
    project_events.publish(project_id, "sandbox.run_completed", {"runId": run.id, "status": run.status, "taskId": run.task_id})
    return sandbox_run_response(run)


@router.get("/projects/{project_id}/sandbox/runs", response_model=list[SandboxRunResponse])
def list_sandbox_runs(
    project_id: str,
    run_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SandboxRunResponse]:
    get_project_or_404(db, project_id)
    statement = select(SandboxRun).where(SandboxRun.project_id == project_id)
    if run_status:
        statement = statement.where(SandboxRun.status == run_status)
    items = db.scalars(statement.order_by(SandboxRun.created_at.desc()).limit(limit)).all()
    return [sandbox_run_response(item) for item in items]


@router.get("/projects/{project_id}/sandbox/runs/{run_id}", response_model=SandboxRunResponse)
def get_sandbox_run(project_id: str, run_id: str, db: Session = Depends(get_db)) -> SandboxRunResponse:
    item = db.scalar(select(SandboxRun).where(SandboxRun.id == run_id, SandboxRun.project_id == project_id))
    if not item:
        raise not_found("沙箱运行", run_id)
    return sandbox_run_response(item)


@router.post(
    "/projects/{project_id}/skills/{skill_name}/execute",
    response_model=SandboxRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_skill(
    project_id: str,
    skill_name: str,
    payload: SkillExecuteRequest,
    db: Session = Depends(get_db),
) -> SandboxRunResponse:
    get_project_or_404(db, project_id)
    if payload.task_id:
        get_task_or_404(db, project_id, payload.task_id)
    skill = skill_registry.get(skill_name)
    skill_registry.validate_input(skill, payload.input)
    code = skill_registry.read_entrypoint(skill)
    run = sandbox_manager.execute_and_record(
        db, project_id=project_id, code=code,
        stdin=json.dumps(payload.input, ensure_ascii=False), task_id=payload.task_id,
        skill_name=skill.name, input_json=payload.input,
        timeout_seconds=payload.timeout_seconds,
    )
    if payload.remember_result and run.status == "completed":
        memory_service.create(db, project_id, MemoryCreate(
            agent_key=(skill.agent_types[0] if skill.agent_types else "project-manager"),
            scope="project", memory_type="episodic",
            key=f"skill:{skill.name}:{run.id[-8:]}",
            content=f"Skill {skill.display_name} 执行结果：{json.dumps(run.result_json, ensure_ascii=False)[:8000]}",
            importance=0.65, tags=["skill-result", skill.name],
            metadata={"sandboxRunId": run.id, "skillVersion": skill.version},
        ))
    if payload.task_id:
        db.add(TaskLog(
            task_id=payload.task_id,
            level="success" if run.status == "completed" else "error",
            event_type="skill_execution",
            message=f"Skill {skill.display_name} { '执行完成' if run.status == 'completed' else '执行失败' }。",
            metadata_json={"skill": skill.name, "version": skill.version, "sandboxRunId": run.id},
        ))
    db.commit()
    db.refresh(run)
    project_events.publish(project_id, "agent.skill_executed", {"skill": skill.name, "runId": run.id, "status": run.status})
    return sandbox_run_response(run)


@router.get("/projects/{project_id}/agents/{agent_key}/context", response_model=AgentContextResponse)
def get_agent_context(
    project_id: str,
    agent_key: str,
    query: str | None = Query(default=None, max_length=1000),
    db: Session = Depends(get_db),
) -> AgentContextResponse:
    get_project_or_404(db, project_id)
    context = agent_runtime.build_context(db, project_id, agent_key, query)
    db.commit()
    return AgentContextResponse(
        project_id=project_id,
        agent_key=agent_key,
        memories=[memory_response(item) for item in context["memories"]],
        skills=[SkillManifestResponse(**item.to_dict()) for item in context["skills"]],
        memory_prompt=context["memory_prompt"],
        skill_prompt=context["skill_prompt"],
        sandbox=SandboxStatusResponse(**context["sandbox"]),
    )
