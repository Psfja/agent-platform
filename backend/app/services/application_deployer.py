from __future__ import annotations

import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AgentBuild, ApplicationDeployment, Artifact, DeploymentRuntimeLog, Iteration, Project, VersionSnapshot
from app.services.docker_runtime import DockerRuntime, docker_runtime
from app.services.task_queue import persistent_queue
from app.services.integrations import notification_service
from app.services.generated_database import generated_database_manager


class ApplicationDeploymentRunner:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="app-deploy")
        self.session_factory = SessionLocal
        self.runtime: DockerRuntime = docker_runtime

    def submit(self, deployment_id: str) -> None:
        persistent_queue.enqueue("application_deployment", {"deployment_id": deployment_id}, fallback=lambda: self.run_sync(deployment_id), priority=4)

    def run_sync(self, deployment_id: str) -> None:
        with self.session_factory() as db:
            deployment = db.get(ApplicationDeployment, deployment_id)
            if not deployment:
                return
            build = db.get(AgentBuild, deployment.build_id)
            project = db.get(Project, deployment.project_id)
            if not build or not project:
                return
            workspace = Path(build.workspace_path).resolve()
            slug = self._slug(f"{project.id}-{deployment.id[-8:]}")
            deployment.backend_image = f"agent-app-{slug}-backend:{deployment.version}"
            deployment.frontend_image = f"agent-app-{slug}-frontend:{deployment.version}"
            deployment.backend_container = f"agent-{slug}-backend"
            deployment.frontend_container = f"agent-{slug}-frontend"
            deployment.network_name = f"agent-{slug}-net"
            deployment.status = "building"
            deployment.started_at = datetime.now(timezone.utc)
            deployment.resource_limits = {
                "backendMemoryMb": self.runtime.settings.deployment_backend_memory_mb,
                "frontendMemoryMb": self.runtime.settings.deployment_frontend_memory_mb,
                "backendCpu": 1,
                "frontendCpu": 0.5,
            }
            project.status = "deploying"
            self._stage(db, deployment, "preparing", 8, "正在生成受控 Dockerfile 与 Nginx 反向代理配置。")
            db.commit()
            try:
                if not self.runtime.available:
                    raise RuntimeError("Docker daemon is not available")
                self.runtime.write_deployment_files(workspace)
                if deployment.rollback_of_id and generated_database_manager.configured:
                    previous = db.get(ApplicationDeployment, deployment.rollback_of_id)
                    backup_path = ((previous.resource_limits or {}).get("database") or {}).get("backup", {}).get("filePath") if previous else None
                    if backup_path:
                        generated_database_manager.restore(backup_path)
                        self._log(db, deployment, "database_rollback", "success", "业务 PostgreSQL 已恢复到目标版本部署前快照。", {"backupPath": backup_path})
                self._stage(db, deployment, "database_migration", 15, "正在备份业务数据库并执行 Alembic 迁移。")
                db.commit()
                database_info = generated_database_manager.prepare_and_migrate(deployment.project_id, deployment.id, workspace / "backend")
                deployment.resource_limits = {**deployment.resource_limits, "database": database_info}

                self._stage(db, deployment, "building_backend", 25, "正在构建 FastAPI 后端镜像。")
                db.commit()
                result = self.runtime.build_image(workspace / "backend", "Dockerfile.agent", deployment.backend_image)
                self._log(db, deployment, "building_backend", "success", f"后端镜像构建完成：{deployment.backend_image}", {"elapsedMs": result.elapsed_ms})

                self._stage(db, deployment, "building_frontend", 46, "正在构建 Vue + Nginx 前端镜像。")
                db.commit()
                result = self.runtime.build_image(workspace / "frontend", "Dockerfile.agent", deployment.frontend_image)
                self._log(db, deployment, "building_frontend", "success", f"前端镜像构建完成：{deployment.frontend_image}", {"elapsedMs": result.elapsed_ms})

                self._stage(db, deployment, "starting", 68, "正在创建隔离网络并启动应用容器。")
                db.commit()
                self.runtime.create_network(deployment.network_name)
                self.runtime.run_backend(deployment.backend_container, deployment.backend_image, deployment.network_name, database_info.get("databaseUrl") if database_info.get("configured") else None)
                self.runtime.run_frontend(deployment.frontend_container, deployment.frontend_image, deployment.network_name)
                port = self.runtime.host_port(deployment.frontend_container)
                deployment.host_port = port
                deployment.deploy_url = f"http://{self.runtime.settings.deployment_public_host}:{port}"
                deployment.health_url = f"{deployment.deploy_url}/health"
                self._log(db, deployment, "starting", "success", f"应用容器已启动，临时访问地址：{deployment.deploy_url}")

                self._stage(db, deployment, "smoke_testing", 84, "正在执行前端首页和后端健康检查。")
                db.commit()
                smoke = self.runtime.smoke_test(deployment.deploy_url)
                deployment.smoke_result = smoke
                if not smoke.get("passed"):
                    backend_logs = self.runtime.logs(deployment.backend_container)
                    frontend_logs = self.runtime.logs(deployment.frontend_container)
                    raise RuntimeError(f"Smoke test failed: {smoke.get('error', smoke)}\nBackend: {backend_logs[-1500:]}\nFrontend: {frontend_logs[-1500:]}")
                self._log(db, deployment, "smoke_testing", "success", "冒烟测试通过：首页与 /health 均可访问。", smoke)

                previous = db.scalar(select(ApplicationDeployment).where(
                    ApplicationDeployment.project_id == deployment.project_id,
                    ApplicationDeployment.environment == deployment.environment,
                    ApplicationDeployment.status == "running",
                    ApplicationDeployment.id != deployment.id,
                ).order_by(ApplicationDeployment.created_at.desc()))
                if previous:
                    deployment.previous_deployment_id = previous.id
                    self.stop_runtime(previous)
                    previous.status = "stopped"
                    previous.current_stage = "replaced"
                    previous.updated_at = datetime.now(timezone.utc)
                    self._log(db, deployment, "switching", "info", f"新版本已验证，旧部署 {previous.version} 已停止；旧镜像继续保留用于回滚。")

                deployment.status = "running"
                deployment.current_stage = "completed"
                deployment.progress = 100
                deployment.finished_at = datetime.now(timezone.utc)
                project.status = "completed"
                project.extra_config = {**(project.extra_config or {}), f"{deployment.environment}DeploymentId": deployment.id, "lastDeployUrl": deployment.deploy_url}
                project.updated_at = datetime.now(timezone.utc)
                if build.iteration_id:
                    iteration = db.get(Iteration, build.iteration_id)
                    if iteration:
                        iteration.status = "completed"
                        iteration.deploy_status = f"已部署：{deployment.deploy_url}"
                        iteration.finished_at = datetime.now(timezone.utc)
                        db.execute(update(VersionSnapshot).where(VersionSnapshot.project_id == deployment.project_id).values(is_current=False))
                        snapshot = db.scalar(select(VersionSnapshot).where(VersionSnapshot.project_id == deployment.project_id, VersionSnapshot.iteration_id == iteration.id))
                        if snapshot:
                            snapshot.docker_image_tag = deployment.frontend_image
                            snapshot.deploy_config_snapshot = {"deploymentId": deployment.id, "url": deployment.deploy_url, "backendImage": deployment.backend_image, "frontendImage": deployment.frontend_image, "environment": deployment.environment}
                            snapshot.is_current = True
                        project.version = iteration.version
                db.add(Artifact(
                    project_id=deployment.project_id, name=f"Deployment {deployment.version}",
                    artifact_type="deployment", path=deployment.deploy_url, size_bytes=0,
                    metadata_json={"deploymentId": deployment.id, "buildId": deployment.build_id, "environment": deployment.environment, "backendImage": deployment.backend_image, "frontendImage": deployment.frontend_image},
                ))
                self._log(db, deployment, "completed", "success", f"部署完成：{deployment.deploy_url}")
                notification_service.notify(db, project, "deployment.completed", "应用部署成功", f"版本 {deployment.version} 已部署：{deployment.deploy_url}")
                db.commit()
            except Exception as exc:
                db.rollback()
                deployment = db.get(ApplicationDeployment, deployment_id)
                project = db.get(Project, deployment.project_id) if deployment else None
                if not deployment:
                    return
                self.cleanup_runtime(deployment)
                deployment.status = "failed"
                deployment.current_stage = "failed"
                deployment.error_message = str(exc)[:8000]
                deployment.finished_at = datetime.now(timezone.utc)
                if project:
                    previous_status = (project.extra_config or {}).get("deploymentPreviousStatus", "completed")
                    project.status = previous_status
                if build and build.iteration_id:
                    iteration = db.get(Iteration, build.iteration_id)
                    if iteration:
                        iteration.status = "failed"; iteration.deploy_status = f"部署失败：{deployment.error_message[:500]}"; iteration.finished_at = datetime.now(timezone.utc)
                self._log(db, deployment, "failed", "error", deployment.error_message, {"trace": traceback.format_exc()[-4000:]})
                db.commit()

    def stop_runtime(self, deployment: ApplicationDeployment) -> None:
        self.runtime.stop_remove(deployment.frontend_container)
        self.runtime.stop_remove(deployment.backend_container)
        self.runtime.remove_network(deployment.network_name)

    def cleanup_runtime(self, deployment: ApplicationDeployment) -> None:
        try:
            self.stop_runtime(deployment)
        except Exception:
            pass

    def _stage(self, db: Session, deployment: ApplicationDeployment, stage: str, progress: int, message: str) -> None:
        deployment.current_stage = stage
        deployment.progress = progress
        deployment.updated_at = datetime.now(timezone.utc)
        self._log(db, deployment, stage, "info", message)

    @staticmethod
    def _log(db: Session, deployment: ApplicationDeployment, stage: str, level: str, message: str, metadata: dict | None = None) -> None:
        db.add(DeploymentRuntimeLog(deployment_id=deployment.id, stage=stage, level=level, message=message, metadata_json=metadata or {}))
        db.flush()

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")[:48]


def recover_stale_deployments(db: Session) -> int:
    stale = db.scalars(select(ApplicationDeployment).where(ApplicationDeployment.status.in_(["pending", "building", "deploying"]))).all()
    for item in stale:
        item.status = "failed"
        item.current_stage = "failed"
        item.error_message = "API 服务重启导致部署中断，请重新部署。"
        item.finished_at = datetime.now(timezone.utc)
        db.add(DeploymentRuntimeLog(deployment_id=item.id, stage="failed", level="error", message=item.error_message, metadata_json={"recoverable": True}))
    if stale:
        db.commit()
    return len(stale)


application_deployment_runner = ApplicationDeploymentRunner()
