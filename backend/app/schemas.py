from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class LoginRequest(APIModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class RefreshRequest(APIModel):
    refresh_token: str


class LogoutRequest(APIModel):
    refresh_token: str


class UserResponse(APIModel):
    id: str
    email: str
    display_name: str
    platform_role: str
    department: str
    is_active: bool
    auth_source: str
    last_login_at: datetime | None


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ProjectMemberCreate(APIModel):
    email: str = Field(min_length=5, max_length=255)
    role: Literal["co_manager", "member", "viewer"] = "member"


class ProjectMemberResponse(APIModel):
    id: str
    user_id: str
    email: str
    display_name: str
    department: str
    role: str
    status: str
    joined_at: datetime


class SSOStatusResponse(APIModel):
    oidc_configured: bool
    ldap_configured: bool
    providers: list[str]


class AdminUserCreate(APIModel):
    email: str = Field(min_length=5, max_length=255)
    display_name: str = Field(min_length=2, max_length=80)
    department: str = Field(default="", max_length=120)
    platform_role: Literal["super_admin", "platform_admin", "user"] = "user"
    initial_password: str | None = Field(default=None, min_length=8, max_length=200)


class AdminUserUpdate(APIModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    department: str | None = Field(default=None, max_length=120)
    platform_role: Literal["super_admin", "platform_admin", "user"] | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=200)


class AdminUserResponse(APIModel):
    id: str
    email: str
    display_name: str
    department: str
    platform_role: str
    is_active: bool
    auth_source: str
    last_login_at: datetime | None
    created_at: datetime
    project_count: int


class AdminUserCreatedResponse(APIModel):
    user: AdminUserResponse
    temp_password: str | None


class LDAPLoginRequest(APIModel):
    username: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class OIDCCallbackRequest(APIModel):
    code: str
    state: str


class AgentTypeCreate(APIModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,79}$")
    display_name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=5000)
    system_prompt: str = Field(min_length=2, max_length=100000)
    model: str = Field(min_length=2, max_length=160)
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    sandbox_config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AgentTypeUpdate(APIModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=2, max_length=5000)
    system_prompt: str | None = Field(default=None, min_length=2, max_length=100000)
    model: str | None = Field(default=None, min_length=2, max_length=160)
    tools: list[str] | None = None
    skills: list[str] | None = None
    sandbox_config: dict[str, Any] | None = None
    is_active: bool | None = None


class AgentTypeResponse(APIModel):
    id: str
    name: str
    display_name: str
    description: str
    system_prompt: str
    model: str
    tools: list[str]
    skills: list[str]
    sandbox_config: dict[str, Any]
    version: int
    is_template: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PipelineNodeInput(APIModel):
    node_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    agent_type_id: str
    display_name: str
    depends_on: list[str] = Field(default_factory=list)
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    config: dict[str, Any] = Field(default_factory=dict)
    position: int = 0


class PipelineTemplateCreate(APIModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,79}$")
    display_name: str
    description: str
    template_type: Literal["fullstack", "api", "frontend", "custom"] = "custom"
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    nodes: list[PipelineNodeInput] = Field(default_factory=list)


class PipelineTemplateResponse(APIModel):
    id: str
    name: str
    display_name: str
    description: str
    template_type: str
    version: int
    is_active: bool
    is_system: bool
    config: dict[str, Any]
    nodes: list[PipelineNodeInput]
    created_at: datetime
    updated_at: datetime


class RequirementCreate(APIModel):
    title: str = "项目需求说明书"
    content_markdown: str = Field(min_length=10, max_length=200000)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "confirmed"] = "draft"
    change_summary: str = ""


class RequirementResponse(APIModel):
    id: str
    project_id: str
    version: int
    title: str
    content_markdown: str
    structured_data: dict[str, Any]
    status: str
    change_summary: str
    created_by: str | None
    created_at: datetime


class DocumentCreate(APIModel):
    document_type: Literal["requirements", "architecture", "api", "database", "deployment", "test_report"]
    title: str
    content_markdown: str = Field(min_length=1, max_length=500000)
    source_build_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(APIModel):
    id: str
    project_id: str
    document_type: str
    version: int
    title: str
    content_markdown: str
    source_build_id: str | None
    metadata: dict[str, Any]
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class ClarificationCreate(APIModel):
    question: str = Field(min_length=2, max_length=5000)
    requirement_version_id: str | None = None


class ClarificationAnswer(APIModel):
    answer: str = Field(min_length=1, max_length=10000)


class TaskCount(APIModel):
    done: int
    total: int


class ProjectCreate(APIModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=5000)
    template: str = Field(default="Web 全栈应用", max_length=64)
    auto_build: bool = False

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    risk: Literal["low", "medium", "high"] | None = None


class ProjectSummary(APIModel):
    id: str
    name: str
    description: str
    status: str
    progress: int
    version: str
    template: str
    owner: str
    updated_at: datetime
    members: list[str]
    tasks: TaskCount
    risk: str


class ProjectActionRequest(APIModel):
    action: Literal["pause", "resume", "archive", "restore"]


class TaskSummary(APIModel):
    id: str
    parent_id: str | None
    name: str
    agent: str
    agent_short: str
    status: str
    progress: int
    duration: str
    started_at: datetime | None
    incremental: bool
    description: str
    files: int
    tokens: str
    current_action: str = ""
    iteration_id: str | None = None


class TaskActionRequest(APIModel):
    action: Literal["pause", "resume", "cancel", "retry"]


class LogResponse(APIModel):
    id: str
    time: datetime
    type: str
    event_type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterventionCreate(APIModel):
    content: str = Field(min_length=2, max_length=4000)
    intervention_type: Literal["instruction", "redo", "pause", "resume", "terminate"] = "instruction"

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        return value.strip()


class InterventionResponse(APIModel):
    id: str
    task_id: str
    actor_name: str
    intervention_type: str
    content: str
    status: str
    agent_response: str
    created_at: datetime
    processed_at: datetime | None


class ImpactAnalysisRequest(APIModel):
    change_request: str = Field(min_length=20, max_length=5000)

    @field_validator("change_request")
    @classmethod
    def strip_request(cls, value: str) -> str:
        return value.strip()


class ImpactModule(APIModel):
    name: str
    change: str
    risk: Literal["low", "medium", "high"] = "low"


class ImpactAnalysis(APIModel):
    iteration_id: str
    proposed_version: str
    risk_level: Literal["low", "medium", "high"]
    change_type: Literal["feature", "fix", "architecture"]
    summary: str
    modules: list[ImpactModule]
    estimated_files: dict[str, int]
    database_change: bool
    database_strategy: str
    existing_api_impact: bool
    breaking_changes: list[str]
    suggested_agents: list[str]
    estimated_tasks: int
    recommendations: list[str]


class IterationResponse(APIModel):
    id: str
    version: str
    title: str
    description: str
    date: datetime
    author: str
    status: str
    files: int
    added: int
    removed: int
    tests: float
    deploy_status: str
    type: str
    impact_analysis: dict[str, Any] = Field(default_factory=dict)


class ConfirmIterationRequest(APIModel):
    approved: bool = True


class VersionResponse(APIModel):
    id: str
    version: str
    is_current: bool
    docker_image_tag: str
    created_at: datetime


class CompareResponse(APIModel):
    from_version: str
    to_version: str
    summary: dict[str, int]
    files: list[dict[str, Any]]
    schema_changes: list[dict[str, Any]]
    api_changes: list[dict[str, Any]]
    feature_changes: dict[str, list[str]]
    has_breaking_changes: bool


class RollbackRequest(APIModel):
    confirm_data_risk: bool = False


class RollbackResponse(APIModel):
    operation_id: str
    target_version: str
    status: str
    steps: list[str]


class ArtifactResponse(APIModel):
    id: str
    name: str
    type: str
    path: str
    size_bytes: int
    metadata: dict[str, Any]
    created_at: datetime


class DashboardResponse(APIModel):
    project: ProjectSummary
    active_tasks: list[TaskSummary]
    metrics: dict[str, int | float]
    health: dict[str, Any]
    recent_activity: list[dict[str, Any]]


class PaginatedResponse(APIModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 50


class EventEnvelope(APIModel):
    event: str
    project_id: str
    data: dict[str, Any]
    timestamp: datetime


class MemoryCreate(APIModel):
    agent_key: str = Field(default="project-manager", min_length=2, max_length=80)
    scope: Literal["project", "agent", "working"] = "project"
    memory_type: Literal["semantic", "episodic", "procedural", "working"] = "semantic"
    key: str = Field(min_length=2, max_length=160)
    content: str = Field(min_length=2, max_length=20000)
    importance: float = Field(default=0.5, ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None

    @field_validator("agent_key", "key", "content")
    @classmethod
    def normalize_memory_text(cls, value: str) -> str:
        return value.strip()


class MemoryUpdate(APIModel):
    content: str | None = Field(default=None, min_length=2, max_length=20000)
    importance: float | None = Field(default=None, ge=0, le=1)
    tags: list[str] | None = Field(default=None, max_length=20)
    metadata: dict[str, Any] | None = None
    expires_at: datetime | None = None


class MemoryResponse(APIModel):
    id: str
    project_id: str
    agent_key: str
    scope: str
    memory_type: str
    key: str
    content: str
    importance: float
    tags: list[str]
    metadata: dict[str, Any]
    access_count: int
    last_accessed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SkillManifestResponse(APIModel):
    name: str
    display_name: str
    version: str
    description: str
    entrypoint: str | None
    instructions: str
    agent_types: list[str]
    tags: list[str]
    input_schema: dict[str, Any]
    path: str
    executable: bool
    checksum: str


class SkillExecuteRequest(APIModel):
    input: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    remember_result: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)


class SandboxExecuteRequest(APIModel):
    language: Literal["python"] = "python"
    code: str = Field(min_length=1, max_length=100000)
    stdin: str = Field(default="", max_length=100000)
    task_id: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)


class SandboxRunResponse(APIModel):
    id: str
    project_id: str
    task_id: str | None
    skill_name: str | None
    backend: str
    language: str
    command: list[str]
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    input: dict[str, Any]
    result: dict[str, Any]
    resource_usage: dict[str, Any]
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class SandboxStatusResponse(APIModel):
    configured_backend: str
    active_backend: str
    available: bool
    isolation: str
    docker_available: bool
    limits: dict[str, int | str]
    warnings: list[str]


class AgentContextResponse(APIModel):
    project_id: str
    agent_key: str
    memories: list[MemoryResponse]
    skills: list[SkillManifestResponse]
    memory_prompt: str
    skill_prompt: str
    sandbox: SandboxStatusResponse


class AgentBuildCreate(APIModel):
    requirement: str = Field(min_length=20, max_length=20000)
    template: Literal["fullstack"] = "fullstack"
    mode: Literal["initial", "incremental"] = "initial"
    base_build_id: str | None = None
    auto_deploy: bool = False
    deploy_environment: Literal["test", "production"] = "test"
    engine: Literal["deepagents", "staged"] | None = None
    model: str | None = Field(default=None, max_length=160)
    max_fix_attempts: int = Field(default=2, ge=0, le=5)
    iteration_id: str | None = None

    @field_validator("requirement")
    @classmethod
    def normalize_build_requirement(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_incremental_base(self):
        if self.mode == "incremental" and not self.base_build_id:
            raise ValueError("incremental mode requires base_build_id")
        return self


class HITLDecisionRequest(APIModel):
    decision: Literal["approve", "reject", "edit"]
    edited_arguments: dict[str, Any] | None = None
    reason: str = Field(default="", max_length=2000)


class BuildInstructionCreate(APIModel):
    content: str = Field(min_length=2, max_length=4000)

    @field_validator("content")
    @classmethod
    def normalize_instruction(cls, value: str) -> str:
        return value.strip()


class AgentBuildLogResponse(APIModel):
    id: str
    stage: str
    level: str
    agent_key: str | None
    message: str
    metadata: dict[str, Any]
    created_at: datetime


class AgentBuildResponse(APIModel):
    id: str
    project_id: str
    iteration_id: str | None
    requirement: str
    template: str
    mode: str
    base_build_id: str | None
    model: str
    status: str
    current_stage: str
    progress: int
    plan: dict[str, Any]
    generated_files: list[dict[str, Any]]
    changed_files_count: int
    coverage: float | None
    test_results: list[dict[str, Any]]
    attempt: int
    max_fix_attempts: int
    prompt_tokens: int
    completion_tokens: int
    workspace_path: str
    artifact_path: str
    error_message: str
    cancellation_requested: bool
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    logs: list[AgentBuildLogResponse] = Field(default_factory=list)


class AgentBuildFileResponse(APIModel):
    path: str
    size: int
    content: str | None = None


class LLMStatusResponse(APIModel):
    configured: bool
    provider: str
    base_url: str
    model: str
    timeout_seconds: int
    supports_real_execution: bool
    message: str
    agent_engine: str = "staged"
    native_deepagents: bool = False


class ApplicationDeploymentCreate(APIModel):
    build_id: str
    environment: Literal["test", "production"] = "test"


class DeploymentRuntimeLogResponse(APIModel):
    id: str
    stage: str
    level: str
    message: str
    metadata: dict[str, Any]
    created_at: datetime


class ApplicationDeploymentResponse(APIModel):
    id: str
    project_id: str
    build_id: str
    environment: str
    version: str
    status: str
    current_stage: str
    progress: int
    backend_image: str
    frontend_image: str
    backend_container: str
    frontend_container: str
    network_name: str
    host_port: int | None
    deploy_url: str
    health_url: str
    smoke_result: dict[str, Any]
    resource_limits: dict[str, Any]
    previous_deployment_id: str | None
    rollback_of_id: str | None
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    logs: list[DeploymentRuntimeLogResponse] = Field(default_factory=list)


class DeploymentRuntimeStatusResponse(APIModel):
    docker_available: bool
    docker_version: str
    ready: bool
    message: str
    running_deployments: int


class ConversationCreate(APIModel):
    agent_key: str = Field(min_length=2, max_length=80)
    title: str = Field(default="", max_length=200)


class ConversationUpdate(APIModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationMessageResponse(APIModel):
    id: str
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime


class ConversationResponse(APIModel):
    id: str
    project_id: str
    agent_key: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    message_count: int


class ConversationDetailResponse(ConversationResponse):
    messages: list[ConversationMessageResponse]


class ConversationMessageCreate(APIModel):
    content: str = Field(min_length=1, max_length=20000)
    remember: bool = True


class ChatTurnResponse(APIModel):
    conversation: ConversationResponse
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
    memories_used: list[MemoryResponse]
    context: dict[str, Any]
