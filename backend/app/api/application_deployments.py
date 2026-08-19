from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.agent_builds import get_build_or_404
from app.api.projects import get_project_or_404
from app.core.errors import AppError, conflict, not_found
from app.database import get_db
from app.models import ApplicationDeployment, uuid_str
from app.schemas import ApplicationDeploymentCreate, ApplicationDeploymentResponse, DeploymentRuntimeStatusResponse
from app.serializers import application_deployment_response
from app.services.application_deployer import application_deployment_runner
from app.services.docker_runtime import docker_runtime

router = APIRouter(tags=["application-deployments"])


def get_deployment_or_404(db: Session, project_id: str, deployment_id: str) -> ApplicationDeployment:
    item = db.scalar(select(ApplicationDeployment).where(ApplicationDeployment.id == deployment_id, ApplicationDeployment.project_id == project_id))
    if not item:
        raise not_found("应用部署", deployment_id)
    return item


@router.get("/deployment-runtime/status", response_model=DeploymentRuntimeStatusResponse)
def deployment_runtime_status(db: Session = Depends(get_db)) -> DeploymentRuntimeStatusResponse:
    info = docker_runtime.status()
    running = db.scalar(select(func.count(ApplicationDeployment.id)).where(ApplicationDeployment.status == "running")) or 0
    return DeploymentRuntimeStatusResponse(**info, running_deployments=running)


@router.post("/projects/{project_id}/application-deployments", response_model=ApplicationDeploymentResponse, status_code=status.HTTP_202_ACCEPTED)
def create_application_deployment(project_id: str, payload: ApplicationDeploymentCreate, db: Session = Depends(get_db)) -> ApplicationDeploymentResponse:
    project = get_project_or_404(db, project_id)
    build = get_build_or_404(db, project_id, payload.build_id)
    if build.status != "completed" or not build.workspace_path:
        raise conflict("BUILD_NOT_DEPLOYABLE", "只有已完成并通过质量门禁的构建可以部署", buildStatus=build.status)
    if not docker_runtime.available:
        raise AppError(503, "DOCKER_NOT_AVAILABLE", "未检测到可用 Docker daemon，无法部署生成应用")
    active = db.scalar(select(ApplicationDeployment).where(
        ApplicationDeployment.project_id == project_id,
        ApplicationDeployment.environment == payload.environment,
        ApplicationDeployment.status.in_(["pending", "building", "deploying"]),
    ))
    if active:
        raise conflict("DEPLOYMENT_ALREADY_RUNNING", "该环境已有部署任务正在执行", deploymentId=active.id)
    item = ApplicationDeployment(
        id=f"app-deploy-{uuid_str()}", project_id=project_id, build_id=build.id,
        environment=payload.environment, version=f"build-{build.id[-8:]}",
        status="pending", current_stage="queued", progress=0,
    )
    db.add(item)
    project.extra_config = {**(project.extra_config or {}), "deploymentPreviousStatus": project.status, "activeDeploymentId": item.id}
    project.status = "deploying"
    db.commit()
    db.refresh(item)
    response = application_deployment_response(item)
    application_deployment_runner.submit(item.id)
    return response


@router.get("/projects/{project_id}/application-deployments", response_model=list[ApplicationDeploymentResponse])
def list_application_deployments(project_id: str, db: Session = Depends(get_db)) -> list[ApplicationDeploymentResponse]:
    get_project_or_404(db, project_id)
    items = db.scalars(select(ApplicationDeployment).where(ApplicationDeployment.project_id == project_id).order_by(ApplicationDeployment.created_at.desc())).all()
    return [application_deployment_response(item, include_logs=False) for item in items]


@router.get("/projects/{project_id}/application-deployments/{deployment_id}", response_model=ApplicationDeploymentResponse)
def get_application_deployment(project_id: str, deployment_id: str, db: Session = Depends(get_db)) -> ApplicationDeploymentResponse:
    return application_deployment_response(get_deployment_or_404(db, project_id, deployment_id))


@router.post("/projects/{project_id}/application-deployments/{deployment_id}/stop", response_model=ApplicationDeploymentResponse)
def stop_application_deployment(project_id: str, deployment_id: str, db: Session = Depends(get_db)) -> ApplicationDeploymentResponse:
    item = get_deployment_or_404(db, project_id, deployment_id)
    if item.status != "running":
        raise conflict("DEPLOYMENT_NOT_RUNNING", "只有运行中的部署可以停止", status=item.status)
    application_deployment_runner.stop_runtime(item)
    item.status = "stopped"
    item.current_stage = "stopped"
    item.updated_at = datetime.now(timezone.utc)
    project = get_project_or_404(db, project_id)
    project.extra_config = {**(project.extra_config or {}), "activeDeploymentId": None}
    db.commit()
    db.refresh(item)
    return application_deployment_response(item)


@router.post("/projects/{project_id}/application-deployments/{deployment_id}/rollback", response_model=ApplicationDeploymentResponse, status_code=status.HTTP_202_ACCEPTED)
def rollback_application_deployment(project_id: str, deployment_id: str, db: Session = Depends(get_db)) -> ApplicationDeploymentResponse:
    target = get_deployment_or_404(db, project_id, deployment_id)
    get_project_or_404(db, project_id)
    if not docker_runtime.available:
        raise AppError(503, "DOCKER_NOT_AVAILABLE", "未检测到可用 Docker daemon，无法执行回滚")
    current = db.scalar(select(ApplicationDeployment).where(
        ApplicationDeployment.project_id == project_id,
        ApplicationDeployment.environment == target.environment,
        ApplicationDeployment.status == "running",
    ).order_by(ApplicationDeployment.created_at.desc()))
    if current and current.build_id == target.build_id:
        raise conflict("VERSION_ALREADY_RUNNING", "目标构建已经在该环境运行")
    item = ApplicationDeployment(
        id=f"app-deploy-{uuid_str()}", project_id=project_id, build_id=target.build_id,
        environment=target.environment, version=f"rollback-{target.version}",
        status="pending", current_stage="queued", progress=0,
        rollback_of_id=current.id if current else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    response = application_deployment_response(item)
    application_deployment_runner.submit(item.id)
    return response


@router.get("/projects/{project_id}/application-deployments/{deployment_id}/container-logs")
def deployment_container_logs(project_id: str, deployment_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    item = get_deployment_or_404(db, project_id, deployment_id)
    return {
        "backend": docker_runtime.logs(item.backend_container) if item.backend_container else "",
        "frontend": docker_runtime.logs(item.frontend_container) if item.frontend_container else "",
    }
