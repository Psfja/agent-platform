from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import AgentBuild, AgentMemory, ApplicationDeployment, Artifact, Intervention, Iteration, Project, SandboxRun, Task, TaskLog, VersionSnapshot
from app.schemas import (
    AgentBuildLogResponse, AgentBuildResponse, ApplicationDeploymentResponse, ArtifactResponse,
    DeploymentRuntimeLogResponse, InterventionResponse, IterationResponse, LogResponse,
    MemoryResponse, ProjectSummary, SandboxRunResponse, TaskCount, TaskSummary, VersionResponse,
)


def human_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def token_label(value: int) -> str:
    if value <= 0:
        return "—"
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def project_summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        progress=project.progress,
        version=project.version,
        template=project.template,
        owner=project.owner_name,
        updated_at=project.updated_at,
        members=project.members or [],
        tasks=TaskCount(done=project.tasks_done, total=project.tasks_total),
        risk=project.risk,
    )


def task_summary(task: Task) -> TaskSummary:
    return TaskSummary(
        id=task.id,
        parent_id=task.parent_task_id,
        name=task.name,
        agent=task.agent_type,
        agent_short=task.agent_short,
        status=task.status,
        progress=task.progress,
        duration=human_duration(task.duration_seconds),
        started_at=task.started_at,
        incremental=task.task_type == "incremental",
        description=task.description,
        files=task.files_count,
        tokens=token_label(task.token_used),
        current_action=task.current_action,
        iteration_id=task.iteration_id,
    )


def log_response(log: TaskLog) -> LogResponse:
    return LogResponse(
        id=log.id,
        time=log.created_at,
        type=log.level,
        event_type=log.event_type,
        text=log.message,
        metadata=log.metadata_json or {},
    )


def intervention_response(item: Intervention) -> InterventionResponse:
    return InterventionResponse(
        id=item.id,
        task_id=item.task_id,
        actor_name=item.actor_name,
        intervention_type=item.intervention_type,
        content=item.content,
        status=item.status,
        agent_response=item.agent_response,
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


def iteration_response(iteration: Iteration, author: str = "林嘉") -> IterationResponse:
    return IterationResponse(
        id=iteration.id,
        version=iteration.version,
        title=iteration.title,
        description=iteration.description or iteration.change_request,
        date=iteration.started_at,
        author=author,
        status=iteration.status,
        files=iteration.changed_files_count,
        added=iteration.lines_added,
        removed=iteration.lines_removed,
        tests=iteration.test_pass_rate,
        deploy_status=iteration.deploy_status,
        type=iteration.iteration_type,
        impact_analysis=iteration.impact_analysis or {},
    )


def version_response(snapshot: VersionSnapshot) -> VersionResponse:
    return VersionResponse(
        id=snapshot.id,
        version=snapshot.version,
        is_current=snapshot.is_current,
        docker_image_tag=snapshot.docker_image_tag,
        created_at=snapshot.created_at,
    )


def artifact_response(item: Artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=item.id,
        name=item.name,
        type=item.artifact_type,
        path=item.path,
        size_bytes=item.size_bytes,
        metadata=item.metadata_json or {},
        created_at=item.created_at,
    )


def memory_response(item: AgentMemory) -> MemoryResponse:
    return MemoryResponse(
        id=item.id,
        project_id=item.project_id,
        agent_key=item.agent_key,
        scope=item.scope,
        memory_type=item.memory_type,
        key=item.key,
        content=item.content,
        importance=item.importance,
        tags=item.tags or [],
        metadata=item.metadata_json or {},
        access_count=item.access_count,
        last_accessed_at=item.last_accessed_at,
        expires_at=item.expires_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def agent_build_response(item: AgentBuild, include_logs: bool = True) -> AgentBuildResponse:
    meta = (item.plan or {}).get("_meta", {})
    coverage_values = [result.get("coverage") for result in (item.test_results or []) if result.get("coverage") is not None]
    return AgentBuildResponse(
        id=item.id,
        project_id=item.project_id,
        iteration_id=item.iteration_id,
        requirement=item.requirement,
        template=item.template,
        mode=meta.get("mode", "initial"),
        base_build_id=meta.get("baseBuildId"),
        temperature=getattr(item, "temperature", 0.2),
        model=item.model,
        status=item.status,
        current_stage=item.current_stage,
        progress=item.progress,
        plan=item.plan or {},
        generated_files=item.generated_files or [],
        changed_files_count=int(meta.get("changedFilesCount", 0)),
        coverage=float(coverage_values[-1]) if coverage_values else None,
        test_results=item.test_results or [],
        attempt=item.attempt,
        max_fix_attempts=item.max_fix_attempts,
        prompt_tokens=item.prompt_tokens,
        completion_tokens=item.completion_tokens,
        workspace_path=item.workspace_path,
        artifact_path=item.artifact_path,
        error_message=item.error_message,
        cancellation_requested=item.cancellation_requested,
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        logs=[
            AgentBuildLogResponse(
                id=log.id, stage=log.stage, level=log.level, agent_key=log.agent_key,
                message=log.message, metadata=log.metadata_json or {}, created_at=log.created_at,
            )
            for log in sorted(item.logs, key=lambda value: value.created_at)
        ] if include_logs else [],
    )


def application_deployment_response(item: ApplicationDeployment, include_logs: bool = True) -> ApplicationDeploymentResponse:
    return ApplicationDeploymentResponse(
        id=item.id,
        project_id=item.project_id,
        build_id=item.build_id,
        environment=item.environment,
        version=item.version,
        status=item.status,
        current_stage=item.current_stage,
        progress=item.progress,
        backend_image=item.backend_image,
        frontend_image=item.frontend_image,
        backend_container=item.backend_container,
        frontend_container=item.frontend_container,
        network_name=item.network_name,
        host_port=item.host_port,
        deploy_url=item.deploy_url,
        health_url=item.health_url,
        smoke_result=item.smoke_result or {},
        resource_limits=item.resource_limits or {},
        previous_deployment_id=item.previous_deployment_id,
        rollback_of_id=item.rollback_of_id,
        error_message=item.error_message,
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        logs=[
            DeploymentRuntimeLogResponse(
                id=log.id, stage=log.stage, level=log.level, message=log.message,
                metadata=log.metadata_json or {}, created_at=log.created_at,
            )
            for log in sorted(item.logs, key=lambda value: value.created_at)
        ] if include_logs else [],
    )


def sandbox_run_response(item: SandboxRun) -> SandboxRunResponse:
    return SandboxRunResponse(
        id=item.id,
        project_id=item.project_id,
        task_id=item.task_id,
        skill_name=item.skill_name,
        backend=item.backend,
        language=item.language,
        command=item.command or [],
        status=item.status,
        exit_code=item.exit_code,
        stdout=item.stdout,
        stderr=item.stderr,
        input=item.input_json or {},
        result=item.result_json or {},
        resource_usage=item.resource_usage or {},
        error_message=item.error_message,
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
    )
