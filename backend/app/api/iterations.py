from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.core.errors import bad_request, conflict, not_found
from app.database import get_db
from app.models import AgentBuild, Iteration, Project, VersionSnapshot, uuid_str
from app.schemas import (
    AgentBuildCreate, CompareResponse, ConfirmIterationRequest, ImpactAnalysis, ImpactAnalysisRequest,
    IterationResponse, RollbackRequest, RollbackResponse, VersionResponse,
)
from app.serializers import iteration_response, version_response
from app.services.event_bus import project_events
from app.services.impact_analyzer import analyze_change, next_minor_version, title_from_request
from app.services.orchestrator import create_iteration_tasks
from app.services.versioning import compare_versions, get_snapshot

router = APIRouter(tags=["iterations"])


def get_iteration_or_404(db: Session, project_id: str, iteration_id: str) -> Iteration:
    item = db.scalar(select(Iteration).where(Iteration.id == iteration_id, Iteration.project_id == project_id))
    if not item:
        raise not_found("迭代", iteration_id)
    return item


@router.get("/projects/{project_id}/iterations", response_model=list[IterationResponse])
def list_iterations(project_id: str, db: Session = Depends(get_db)) -> list[IterationResponse]:
    project = get_project_or_404(db, project_id)
    rows = db.scalars(select(Iteration).where(Iteration.project_id == project_id).order_by(Iteration.sequence.desc())).all()
    return [iteration_response(item, project.owner_name) for item in rows]


@router.get("/projects/{project_id}/iterations/{iteration_id}", response_model=IterationResponse)
def get_iteration(project_id: str, iteration_id: str, db: Session = Depends(get_db)) -> IterationResponse:
    project = get_project_or_404(db, project_id)
    return iteration_response(get_iteration_or_404(db, project_id, iteration_id), project.owner_name)


@router.post(
    "/projects/{project_id}/iterations/impact-analysis",
    response_model=ImpactAnalysis,
    status_code=status.HTTP_201_CREATED,
)
def create_impact_analysis(project_id: str, payload: ImpactAnalysisRequest, db: Session = Depends(get_db)) -> ImpactAnalysis:
    project = get_project_or_404(db, project_id)
    if project.status in {"archived", "deleted", "failed"}:
        raise bad_request("PROJECT_NOT_ITERABLE", "当前项目状态不能提出增量需求", status=project.status)
    analysis = analyze_change(payload.change_request, project.version)
    existing = set(db.scalars(select(Iteration.version).where(Iteration.project_id == project_id)).all())
    proposed = analysis["proposed_version"]
    while proposed in existing:
        proposed = next_minor_version(proposed)
    analysis["proposed_version"] = proposed
    sequence = (db.scalar(select(func.max(Iteration.sequence)).where(Iteration.project_id == project_id)) or 0) + 1
    item = Iteration(
        id=f"iter-{uuid_str()}",
        project_id=project_id,
        version=proposed,
        sequence=sequence,
        title=title_from_request(payload.change_request),
        change_request=payload.change_request,
        description=payload.change_request,
        impact_analysis=analysis,
        status="analyzing",
        iteration_type=analysis["change_type"],
        deploy_status="等待用户确认",
    )
    db.add(item)
    db.commit()
    project_events.publish(project_id, "iteration.analysis_completed", {"iterationId": item.id, "version": proposed, "riskLevel": analysis["risk_level"]})
    return ImpactAnalysis(iteration_id=item.id, **analysis)


@router.post("/projects/{project_id}/iterations/{iteration_id}/confirm", response_model=IterationResponse)
def confirm_iteration(project_id: str, iteration_id: str, payload: ConfirmIterationRequest, db: Session = Depends(get_db)) -> IterationResponse:
    project = get_project_or_404(db, project_id)
    item = get_iteration_or_404(db, project_id, iteration_id)
    if item.status != "analyzing":
        raise conflict("ITERATION_ALREADY_STARTED", "该迭代已经确认或结束", status=item.status)
    if not payload.approved:
        item.status = "failed"
        item.deploy_status = "用户取消"
        item.finished_at = datetime.now(timezone.utc)
        db.commit()
        project_events.publish(project_id, "iteration.cancelled", {"iterationId": item.id})
        return iteration_response(item, project.owner_name)
    breaking = (item.impact_analysis or {}).get("breaking_changes", [])
    if breaking:
        raise conflict("BREAKING_CHANGE_REQUIRES_REVIEW", "检测到破坏性变更，需要技术审核者确认", breakingChanges=breaking)
    from app.services.llm_client import OpenAICompatibleClient
    if OpenAICompatibleClient().configured:
        from app.api.agent_builds import create_agent_build
        from app.services.docker_runtime import docker_runtime
        base = db.scalar(select(AgentBuild).where(AgentBuild.project_id == project_id, AgentBuild.status == "completed").order_by(AgentBuild.finished_at.desc()))
        analysis = dict(item.impact_analysis or {})
        analysis["automation"] = {"status": "queued", "mode": "incremental" if base else "initial", "baseBuildId": base.id if base else None, "autoDeploy": docker_runtime.available}
        item.impact_analysis = analysis
        item.status = "executing"
        item.deploy_status = "真实 Agent 构建队列中"
        db.commit()
        build = create_agent_build(project_id, AgentBuildCreate(
            requirement=item.change_request, template="fullstack",
            mode="incremental" if base else "initial", base_build_id=base.id if base else None,
            auto_deploy=docker_runtime.available, deploy_environment="test",
            max_fix_attempts=2, iteration_id=item.id,
        ), db)
        analysis = dict(item.impact_analysis or {})
        analysis["automation"] = {**analysis.get("automation", {}), "buildId": build.id}
        item.impact_analysis = analysis
        db.commit()
        project_events.publish(project_id, "iteration.started", {"iterationId": item.id, "version": item.version, "agentBuildId": build.id, "mode": build.mode})
    else:
        agents = (item.impact_analysis or {}).get("suggested_agents", ["后端开发", "代码审查", "测试工程师"])
        created = create_iteration_tasks(db, project, item, agents)
        analysis = dict(item.impact_analysis or {})
        analysis["automation"] = {"status": "blocked", "reason": "LLM_NOT_CONFIGURED", "fallbackTaskCount": len(created)}
        item.impact_analysis = analysis
        item.deploy_status = "等待任务完成（未配置真实模型）"
        db.commit()
        project_events.publish(project_id, "iteration.started", {"iterationId": item.id, "version": item.version, "taskCount": len(created)})
    return iteration_response(item, project.owner_name)


@router.get("/projects/{project_id}/versions", response_model=list[VersionResponse])
def list_versions(project_id: str, db: Session = Depends(get_db)) -> list[VersionResponse]:
    get_project_or_404(db, project_id)
    rows = db.scalars(select(VersionSnapshot).where(VersionSnapshot.project_id == project_id).order_by(VersionSnapshot.created_at.desc())).all()
    return [version_response(item) for item in rows]


@router.get("/projects/{project_id}/versions/compare", response_model=CompareResponse)
def compare(
    project_id: str,
    from_version: str = Query(alias="from"),
    to_version: str = Query(alias="to"),
    db: Session = Depends(get_db),
) -> CompareResponse:
    get_project_or_404(db, project_id)
    if from_version == to_version:
        raise bad_request("VERSIONS_IDENTICAL", "请选择两个不同版本")
    return CompareResponse(**compare_versions(db, project_id, from_version, to_version))


@router.post("/projects/{project_id}/versions/{version}/rollback", response_model=RollbackResponse, status_code=status.HTTP_202_ACCEPTED)
def rollback(project_id: str, version: str, payload: RollbackRequest, db: Session = Depends(get_db)) -> RollbackResponse:
    project = get_project_or_404(db, project_id)
    target = get_snapshot(db, project_id, version)
    current = db.scalar(select(VersionSnapshot).where(VersionSnapshot.project_id == project_id, VersionSnapshot.is_current.is_(True)))
    if current and current.version == version:
        raise bad_request("VERSION_ALREADY_CURRENT", "目标版本已经是当前运行版本")
    if not payload.confirm_data_risk:
        raise conflict(
            "ROLLBACK_CONFIRMATION_REQUIRED",
            "Schema 回退可能导致新版本字段不可用，请确认数据风险后重试",
            targetVersion=version,
            requiresConfirmation=True,
        )
    db.execute(update(VersionSnapshot).where(VersionSnapshot.project_id == project_id).values(is_current=False))
    target.is_current = True
    project.version = version
    project.status = "deploying"
    project.updated_at = datetime.now(timezone.utc)
    sequence = (db.scalar(select(func.max(Iteration.sequence)).where(Iteration.project_id == project_id)) or 0) + 1
    operation_id = f"rollback-{uuid_str()}"
    db.add(Iteration(id=operation_id, project_id=project_id, version=f"{version}-rollback.{sequence}", sequence=sequence, title=f"回滚到 {version}", change_request=f"人工回滚到历史版本 {version}", description="停止当前实例，拉取目标镜像并执行冒烟测试。", status="deploying", iteration_type="fix", deploy_status="回滚中", rollback_to_iteration_id=target.iteration_id))
    db.commit()
    steps = ["停止当前运行实例", f"拉取镜像 {target.docker_image_tag}", "检查数据库兼容性", "启动目标版本", "执行冒烟测试"]
    project_events.publish(project_id, "version.rollback_started", {"operationId": operation_id, "targetVersion": version, "steps": steps})
    return RollbackResponse(operation_id=operation_id, target_version=version, status="deploying", steps=steps)
