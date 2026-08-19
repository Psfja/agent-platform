from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.iterations import get_iteration_or_404
from app.api.projects import get_project_or_404
from app.core.config import get_settings
from app.core.errors import AppError, conflict, not_found
from app.database import get_db
from app.models import AgentBuild, AgentBuildLog, uuid_str
from app.schemas import AgentBuildCreate, AgentBuildFileResponse, AgentBuildLogResponse, AgentBuildResponse, BuildInstructionCreate, HITLDecisionRequest, LLMStatusResponse
from app.serializers import agent_build_response
from app.services.agent_builder import agent_build_runner
from app.services.generated_workspace import GeneratedWorkspace
from app.services.llm_client import OpenAICompatibleClient

router = APIRouter(tags=["real-agent-builds"])


def get_build_or_404(db: Session, project_id: str, build_id: str) -> AgentBuild:
    item = db.scalar(select(AgentBuild).where(AgentBuild.id == build_id, AgentBuild.project_id == project_id))
    if not item:
        raise not_found("Agent 构建", build_id)
    return item


@router.get("/agent-build/status", response_model=LLMStatusResponse)
def agent_build_status() -> LLMStatusResponse:
    info = OpenAICompatibleClient().status()
    return LLMStatusResponse(**info, agent_engine=get_settings().agent_engine, native_deepagents=True)


@router.post("/projects/{project_id}/agent-builds", response_model=AgentBuildResponse, status_code=status.HTTP_202_ACCEPTED)
def create_agent_build(project_id: str, payload: AgentBuildCreate, db: Session = Depends(get_db)) -> AgentBuildResponse:
    get_project_or_404(db, project_id)
    settings = get_settings()
    model = payload.model or settings.llm_model
    client = OpenAICompatibleClient(model=model)
    if not client.configured:
        raise AppError(503, "LLM_NOT_CONFIGURED", "尚未配置真实模型网关，无法启动 Agent 构建", {"requiredEnv": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]})
    if payload.iteration_id:
        get_iteration_or_404(db, project_id, payload.iteration_id)
    if payload.mode == "incremental":
        base = get_build_or_404(db, project_id, payload.base_build_id or "")
        if base.status != "completed" or not base.workspace_path or not Path(base.workspace_path).is_dir():
            raise conflict("BASE_BUILD_NOT_READY", "增量构建需要一个已完成且源码仍可用的基础版本", baseBuildId=base.id, status=base.status)
    active = db.scalar(select(AgentBuild).where(AgentBuild.project_id == project_id, AgentBuild.status.in_(["pending", "running"])))
    if active:
        raise conflict("AGENT_BUILD_ALREADY_RUNNING", "该项目已有真实 Agent 构建正在执行", buildId=active.id)
    item = AgentBuild(
        id=f"agent-build-{uuid_str()}", project_id=project_id, iteration_id=payload.iteration_id,
        requirement=payload.requirement, template=payload.template, model=model,
        status="pending", current_stage="queued", progress=0, max_fix_attempts=payload.max_fix_attempts,
        plan={"_meta": {"mode": payload.mode, "baseBuildId": payload.base_build_id, "changedFilesCount": 0, "autoDeploy": payload.auto_deploy, "deployEnvironment": payload.deploy_environment, "engine": payload.engine or settings.agent_engine}},
    )
    db.add(item)
    db.flush()
    agent_build_runner.create_tasks(db, item)
    project = get_project_or_404(db, project_id)
    project.extra_config = {**(project.extra_config or {}), "agentBuildPreviousStatus": project.status, "activeAgentBuildId": item.id}
    project.status = "executing"
    project.progress = max(project.progress, 5)
    db.commit()
    db.refresh(item)
    response = agent_build_response(item)
    agent_build_runner.submit(item.id)
    return response


@router.get("/projects/{project_id}/agent-builds", response_model=list[AgentBuildResponse])
def list_agent_builds(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AgentBuildResponse]:
    get_project_or_404(db, project_id)
    items = db.scalars(select(AgentBuild).where(AgentBuild.project_id == project_id).order_by(AgentBuild.created_at.desc()).limit(limit)).all()
    return [agent_build_response(item, include_logs=False) for item in items]


@router.get("/projects/{project_id}/agent-builds/{build_id}", response_model=AgentBuildResponse)
def get_agent_build(project_id: str, build_id: str, db: Session = Depends(get_db)) -> AgentBuildResponse:
    get_project_or_404(db, project_id)
    return agent_build_response(get_build_or_404(db, project_id, build_id))


@router.post("/projects/{project_id}/agent-builds/{build_id}/cancel", response_model=AgentBuildResponse)
def cancel_agent_build(project_id: str, build_id: str, db: Session = Depends(get_db)) -> AgentBuildResponse:
    item = get_build_or_404(db, project_id, build_id)
    if item.status not in {"pending", "running"}:
        raise conflict("AGENT_BUILD_NOT_RUNNING", "只有等待或运行中的构建可以取消", status=item.status)
    item.cancellation_requested = True
    db.commit()
    db.refresh(item)
    return agent_build_response(item)


@router.post("/projects/{project_id}/agent-builds/{build_id}/instructions", response_model=AgentBuildLogResponse, status_code=status.HTTP_202_ACCEPTED)
def instruct_agent_build(project_id: str, build_id: str, payload: BuildInstructionCreate, db: Session = Depends(get_db)) -> AgentBuildLogResponse:
    item = get_build_or_404(db, project_id, build_id)
    if item.status not in {"pending", "running"}:
        raise conflict("AGENT_BUILD_NOT_RUNNING", "构建已结束，不能追加人工指令", status=item.status)
    log = AgentBuildLog(
        build_id=item.id, stage="human", level="human", agent_key=None,
        message=payload.content, metadata_json={"consumed": False},
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return AgentBuildLogResponse(
        id=log.id, stage=log.stage, level=log.level, agent_key=log.agent_key,
        message=log.message, metadata=log.metadata_json, created_at=log.created_at,
    )


@router.post("/projects/{project_id}/agent-builds/{build_id}/hitl", response_model=AgentBuildResponse, status_code=status.HTTP_202_ACCEPTED)
def decide_hitl(project_id: str, build_id: str, payload: HITLDecisionRequest, db: Session = Depends(get_db)) -> AgentBuildResponse:
    item = get_build_or_404(db, project_id, build_id)
    if item.status != "waiting_approval":
        raise conflict("BUILD_NOT_WAITING_APPROVAL", "当前构建没有待处理的 HITL 审批", status=item.status)
    meta = dict((item.plan or {}).get("_meta", {}))
    decision = {"decision": payload.decision, "reason": payload.reason}
    if payload.edited_arguments is not None:
        decision["editedAction"] = {"name": (meta.get("hitlInterrupt") or {}).get("action_requests", [{}])[0].get("name", ""), "args": payload.edited_arguments}
    meta["hitlDecision"] = decision
    meta.pop("hitlInterrupt", None)
    item.plan = {**(item.plan or {}), "_meta": meta}
    item.status = "pending"; item.current_stage = "resuming"
    db.commit(); db.refresh(item)
    response = agent_build_response(item)
    agent_build_runner.submit(item.id)
    return response


@router.post("/projects/{project_id}/agent-builds/{build_id}/retry", response_model=AgentBuildResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_agent_build(project_id: str, build_id: str, db: Session = Depends(get_db)) -> AgentBuildResponse:
    source = get_build_or_404(db, project_id, build_id)
    if source.status not in {"failed", "cancelled"}:
        raise conflict("AGENT_BUILD_NOT_RETRYABLE", "只有失败或已取消的构建可以重试", status=source.status)
    meta = (source.plan or {}).get("_meta", {})
    payload = AgentBuildCreate(
        requirement=source.requirement, template="fullstack",
        mode=meta.get("mode", "initial"), base_build_id=meta.get("baseBuildId"),
        auto_deploy=bool(meta.get("autoDeploy", False)), deploy_environment=meta.get("deployEnvironment", "test"),
        engine=meta.get("engine", "deepagents"), model=source.model, max_fix_attempts=source.max_fix_attempts, iteration_id=source.iteration_id,
    )
    return create_agent_build(project_id, payload, db)


@router.get("/projects/{project_id}/agent-builds/{build_id}/files", response_model=list[AgentBuildFileResponse])
def list_generated_files(project_id: str, build_id: str, db: Session = Depends(get_db)) -> list[AgentBuildFileResponse]:
    item = get_build_or_404(db, project_id, build_id)
    workspace = GeneratedWorkspace(item.project_id, item.id)
    return [AgentBuildFileResponse(path=file["path"], size=file["size"]) for file in workspace.list_files()]


@router.get("/projects/{project_id}/agent-builds/{build_id}/file", response_model=AgentBuildFileResponse)
def read_generated_file(
    project_id: str,
    build_id: str,
    path: str = Query(min_length=1, max_length=500),
    db: Session = Depends(get_db),
) -> AgentBuildFileResponse:
    item = get_build_or_404(db, project_id, build_id)
    workspace = GeneratedWorkspace(item.project_id, item.id)
    content = workspace.read(path)
    return AgentBuildFileResponse(path=path, size=len(content.encode("utf-8")), content=content)


@router.get("/projects/{project_id}/agent-builds/{build_id}/download")
def download_generated_app(project_id: str, build_id: str, db: Session = Depends(get_db)) -> FileResponse:
    item = get_build_or_404(db, project_id, build_id)
    if item.status != "completed" or not item.artifact_path:
        raise conflict("AGENT_BUILD_NOT_READY", "构建尚未完成，暂不能下载", status=item.status)
    archive = Path(item.artifact_path).resolve()
    expected_parent = GeneratedWorkspace(item.project_id, item.id).root.parent
    if not archive.is_file() or archive.parent != expected_parent:
        raise not_found("构建产物", build_id)
    return FileResponse(archive, filename=f"{project_id}-{build_id[-8:]}.zip", media_type="application/zip")
