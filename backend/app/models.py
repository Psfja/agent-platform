from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    platform_role: Mapped[str] = mapped_column(String(32), default="user", index=True)
    department: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auth_source: Mapped[str] = mapped_column(String(24), default="local")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    jti_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24), default="member", index=True)
    invited_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(24), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QueuedJob(Base):
    __tablename__ = "queued_jobs"
    __table_args__ = (Index("ix_queued_job_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    worker_id: Mapped[str | None] = mapped_column(String(120), index=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), default="")
    resource_id: Mapped[str] = mapped_column(String(80), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentType(Base):
    __tablename__ = "agent_types"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(160), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    sandbox_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentTypeVersion(Base):
    __tablename__ = "agent_type_versions"
    __table_args__ = (UniqueConstraint("agent_type_id", "version", name="uq_agent_type_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    agent_type_id: Mapped[str] = mapped_column(ForeignKey("agent_types.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PipelineTemplate(Base):
    __tablename__ = "pipeline_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    template_type: Mapped[str] = mapped_column(String(32), default="custom")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PipelineNode(Base):
    __tablename__ = "pipeline_nodes"
    __table_args__ = (UniqueConstraint("template_id", "node_key", name="uq_pipeline_node_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    template_id: Mapped[str] = mapped_column(ForeignKey("pipeline_templates.id", ondelete="CASCADE"), index=True)
    node_key: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_type_id: Mapped[str] = mapped_column(ForeignKey("agent_types.id", ondelete="RESTRICT"), index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution_mode: Mapped[str] = mapped_column(String(24), default="sequential")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    __table_args__ = (UniqueConstraint("thread_id", "version", name="uq_agent_checkpoint_version"), Index("ix_checkpoint_thread_created", "thread_id", "created_at"))

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DatabaseBackup(Base):
    __tablename__ = "database_backups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    database_type: Mapped[str] = mapped_column(String(24), nullable=False)
    revision: Mapped[str | None] = mapped_column(String(80))
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="completed")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(24), default="in_app")
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RequirementVersion(Base):
    __tablename__ = "requirement_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_requirement_project_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="项目需求说明书")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectDocument(Base):
    __tablename__ = "project_documents"
    __table_args__ = (UniqueConstraint("project_id", "document_type", "version", name="uq_project_document_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(48), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source_build_id: Mapped[str | None] = mapped_column(ForeignKey("agent_builds.id", ondelete="SET NULL"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectAttachment(Base):
    __tablename__ = "project_attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    requirement_version_id: Mapped[str | None] = mapped_column(ForeignKey("requirement_versions.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_provider: Mapped[str] = mapped_column(String(24), default="local")
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RequirementClarification(Base):
    __tablename__ = "requirement_clarifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    requirement_version_id: Mapped[str | None] = mapped_column(ForeignKey("requirement_versions.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(32), default="—")
    template: Mapped[str] = mapped_column(String(64), default="Web 全栈应用")
    owner_id: Mapped[str] = mapped_column(String(64), default="user-linjia")
    owner_name: Mapped[str] = mapped_column(String(64), default="林嘉")
    members: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["LJ"])
    tasks_done: Mapped[int] = mapped_column(Integer, default=0)
    tasks_total: Mapped[int] = mapped_column(Integer, default=0)
    risk: Mapped[str] = mapped_column(String(16), default="low")
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")
    iterations: Mapped[list[Iteration]] = relationship(back_populates="project", cascade="all, delete-orphan")
    snapshots: Mapped[list[VersionSnapshot]] = relationship(back_populates="project", cascade="all, delete-orphan")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="project", cascade="all, delete-orphan")
    memories: Mapped[list[AgentMemory]] = relationship(back_populates="project", cascade="all, delete-orphan")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sandbox_runs: Mapped[list[SandboxRun]] = relationship(back_populates="project", cascade="all, delete-orphan")
    agent_builds: Mapped[list[AgentBuild]] = relationship(back_populates="project", cascade="all, delete-orphan")
    application_deployments: Mapped[list[ApplicationDeployment]] = relationship(back_populates="project", cascade="all, delete-orphan")
    project_members: Mapped[list[ProjectMember]] = relationship(cascade="all, delete-orphan", foreign_keys="ProjectMember.project_id")


class Iteration(Base):
    __tablename__ = "iterations"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_iteration_project_version"),
        UniqueConstraint("project_id", "sequence", name="uq_iteration_project_sequence"),
        Index("ix_iteration_project_status", "project_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    change_request: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    impact_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_files_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0)
    test_pass_rate: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="analyzing")
    iteration_type: Mapped[str] = mapped_column(String(16), default="feature")
    deploy_status: Mapped[str] = mapped_column(String(64), default="尚未部署")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rollback_to_iteration_id: Mapped[str | None] = mapped_column(ForeignKey("iterations.id"))

    project: Mapped[Project] = relationship(back_populates="iterations")
    tasks: Mapped[list[Task]] = relationship(back_populates="iteration")
    snapshots: Mapped[list[VersionSnapshot]] = relationship(back_populates="iteration")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_task_project_status", "project_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    iteration_id: Mapped[str | None] = mapped_column(ForeignKey("iterations.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_short: Mapped[str] = mapped_column(String(8), default="AI")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    task_type: Mapped[str] = mapped_column(String(24), default="initial")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    files_count: Mapped[int] = mapped_column(Integer, default=0)
    token_used: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    current_action: Mapped[str] = mapped_column(Text, default="")
    execution_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    thread_id: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="tasks")
    iteration: Mapped[Iteration | None] = relationship(back_populates="tasks")
    parent: Mapped[Task | None] = relationship(remote_side="Task.id", back_populates="children")
    children: Mapped[list[Task]] = relationship(back_populates="parent")
    logs: Mapped[list[TaskLog]] = relationship(back_populates="task", cascade="all, delete-orphan")
    interventions: Mapped[list[Intervention]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskLog(Base):
    __tablename__ = "task_logs"
    __table_args__ = (Index("ix_task_log_task_created", "task_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    event_type: Mapped[str] = mapped_column(String(32), default="message")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[Task] = relationship(back_populates="logs")


class Intervention(Base):
    __tablename__ = "interventions"
    __table_args__ = (Index("ix_intervention_task_created", "task_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(String(64), default="user-linjia")
    actor_name: Mapped[str] = mapped_column(String(64), default="林嘉")
    intervention_type: Mapped[str] = mapped_column(String(32), default="instruction")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    agent_response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship(back_populates="interventions")


class VersionSnapshot(Base):
    __tablename__ = "version_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_snapshot_project_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    iteration_id: Mapped[str | None] = mapped_column(ForeignKey("iterations.id", ondelete="SET NULL"), index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    code_snapshot_path: Mapped[str] = mapped_column(String(500), default="")
    code_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    db_schema_snapshot: Mapped[str] = mapped_column(Text, default="")
    api_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    docker_image_tag: Mapped[str] = mapped_column(String(255), default="")
    deploy_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="snapshots")
    iteration: Mapped[Iteration | None] = relationship(back_populates="snapshots")


class AgentMemory(Base):
    __tablename__ = "agent_memories"
    __table_args__ = (
        Index("ix_memory_project_agent", "project_id", "agent_key"),
        Index("ix_memory_project_type", "project_id", "memory_type"),
        Index("ix_memory_updated", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    agent_key: Mapped[str] = mapped_column(String(80), default="project-manager", index=True)
    scope: Mapped[str] = mapped_column(String(24), default="project")
    memory_type: Mapped[str] = mapped_column(String(24), default="semantic")
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="memories")


class SandboxRun(Base):
    __tablename__ = "sandbox_runs"
    __table_args__ = (
        Index("ix_sandbox_project_created", "project_id", "created_at"),
        Index("ix_sandbox_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    skill_name: Mapped[str | None] = mapped_column(String(120), index=True)
    backend: Mapped[str] = mapped_column(String(24), default="local")
    language: Mapped[str] = mapped_column(String(24), default="python")
    command: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    workspace_path: Mapped[str] = mapped_column(String(500), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="sandbox_runs")


class AgentBuild(Base):
    __tablename__ = "agent_builds"
    __table_args__ = (
        Index("ix_agent_build_project_created", "project_id", "created_at"),
        Index("ix_agent_build_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    iteration_id: Mapped[str | None] = mapped_column(ForeignKey("iterations.id", ondelete="SET NULL"), index=True)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str] = mapped_column(String(32), default="fullstack")
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    generated_files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    test_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_fix_attempts: Mapped[int] = mapped_column(Integer, default=2)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    workspace_path: Mapped[str] = mapped_column(String(500), default="")
    artifact_path: Mapped[str] = mapped_column(String(500), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="agent_builds")
    logs: Mapped[list[AgentBuildLog]] = relationship(back_populates="build", cascade="all, delete-orphan")


class AgentBuildLog(Base):
    __tablename__ = "agent_build_logs"
    __table_args__ = (Index("ix_agent_build_log_created", "build_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    build_id: Mapped[str] = mapped_column(ForeignKey("agent_builds.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(64), default="system")
    level: Mapped[str] = mapped_column(String(16), default="info")
    agent_key: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    build: Mapped[AgentBuild] = relationship(back_populates="logs")


class ApplicationDeployment(Base):
    __tablename__ = "application_deployments"
    __table_args__ = (
        Index("ix_app_deployment_project_created", "project_id", "created_at"),
        Index("ix_app_deployment_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    build_id: Mapped[str] = mapped_column(ForeignKey("agent_builds.id", ondelete="RESTRICT"), index=True)
    environment: Mapped[str] = mapped_column(String(24), default="test", index=True)
    version: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String(48), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    backend_image: Mapped[str] = mapped_column(String(255), default="")
    frontend_image: Mapped[str] = mapped_column(String(255), default="")
    backend_container: Mapped[str] = mapped_column(String(160), default="")
    frontend_container: Mapped[str] = mapped_column(String(160), default="")
    network_name: Mapped[str] = mapped_column(String(160), default="")
    host_port: Mapped[int | None] = mapped_column(Integer)
    deploy_url: Mapped[str] = mapped_column(String(500), default="")
    health_url: Mapped[str] = mapped_column(String(500), default="")
    smoke_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    previous_deployment_id: Mapped[str | None] = mapped_column(ForeignKey("application_deployments.id", ondelete="SET NULL"))
    rollback_of_id: Mapped[str | None] = mapped_column(ForeignKey("application_deployments.id", ondelete="SET NULL"))
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="application_deployments")
    logs: Mapped[list[DeploymentRuntimeLog]] = relationship(back_populates="deployment", cascade="all, delete-orphan")


class DeploymentRuntimeLog(Base):
    __tablename__ = "deployment_runtime_logs"
    __table_args__ = (Index("ix_deploy_runtime_log_created", "deployment_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("application_deployments.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(48), default="system")
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    deployment: Mapped[ApplicationDeployment] = relationship(back_populates="logs")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    iteration_id: Mapped[str | None] = mapped_column(ForeignKey("iterations.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(500), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="artifacts")


class Conversation(Base):
    """A chat conversation with an agent, scoped to a project, with context management and long-term memory."""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversation_project_updated", "project_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    agent_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="chat", index=True)  # chat | agent（DeepAgents 工具模式）
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )
    interrupts: Mapped[list[ConversationInterrupt]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationInterrupt.created_at"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_conversation_message_created", "conversation_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ConversationInterrupt(Base):
    """Pending human approval raised by the agent-mode conversation (DeepAgents interrupt)."""

    __tablename__ = "conversation_interrupts"
    __table_args__ = (Index("ix_conversation_interrupt_pending", "conversation_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80), default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column("payload", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | decided
    decision: Mapped[str] = mapped_column(String(16), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="interrupts")
