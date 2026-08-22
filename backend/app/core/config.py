from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _load_dotenv(path: Path) -> None:
    """极小的 .env 读取器，避免额外运行时依赖。"""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    api_prefix: str
    database_url: str
    cors_origins: tuple[str, ...]
    seed_demo_data: bool
    sql_echo: bool
    base_dir: Path
    skill_directories: tuple[Path, ...]
    sandbox_backend: str
    sandbox_data_dir: Path
    sandbox_timeout_seconds: int
    sandbox_memory_mb: int
    sandbox_cpu_seconds: int
    sandbox_output_limit: int
    sandbox_docker_image: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: int
    llm_max_retries: int
    agent_build_root: Path
    agent_max_files: int
    agent_max_file_bytes: int
    agent_build_timeout_seconds: int
    agent_build_docker_image: str
    deployment_public_host: str
    deployment_smoke_timeout_seconds: int
    deployment_backend_memory_mb: int
    deployment_frontend_memory_mb: int
    jwt_secret: str
    jwt_algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    redis_url: str
    queue_name: str
    queue_fallback_threads: bool
    run_db_migrations: bool
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    ldap_url: str
    ldap_base_dn: str
    ldap_bind_dn: str
    ldap_bind_password: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    git_remote_url: str
    git_default_branch: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    notification_webhook_url: str
    agent_engine: str
    langgraph_checkpoint_db: Path
    generated_database_url: str
    conversation_context_tokens: int
    embedding_model: str
    conversation_history_min_messages: int
    generated_database_backup_dir: Path

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[2]
    _load_dotenv(base_dir / ".env")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/agent_platform.db")
    if database_url.startswith("sqlite:///./"):
        relative = database_url.removeprefix("sqlite:///./")
        database_url = f"sqlite:///{(base_dir / relative).as_posix()}"
    origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:4173,http://127.0.0.1:4173"
        ).split(",")
        if origin.strip()
    )
    raw_skill_dirs = os.getenv("SKILL_DIRECTORIES", str(base_dir / "skills"))
    skill_paths: list[Path] = []
    for value in raw_skill_dirs.split(","):
        if not value.strip():
            continue
        path = Path(value.strip()).expanduser()
        skill_paths.append((path if path.is_absolute() else base_dir / path).resolve())
    skill_directories = tuple(skill_paths)
    sandbox_path = Path(os.getenv("SANDBOX_DATA_DIR", str(base_dir / "data" / "sandboxes"))).expanduser()
    sandbox_data_dir = (sandbox_path if sandbox_path.is_absolute() else base_dir / sandbox_path).resolve()
    return Settings(
        app_name=os.getenv("APP_NAME", "智构企业智能体平台 API"),
        app_env=os.getenv("APP_ENV", "development"),
        debug=_as_bool(os.getenv("APP_DEBUG"), True),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        database_url=database_url,
        cors_origins=origins,
        seed_demo_data=_as_bool(os.getenv("SEED_DEMO_DATA"), True),
        sql_echo=_as_bool(os.getenv("SQL_ECHO"), False),
        base_dir=base_dir,
        skill_directories=skill_directories,
        sandbox_backend=os.getenv("SANDBOX_BACKEND", "local").strip().lower(),
        sandbox_data_dir=sandbox_data_dir,
        sandbox_timeout_seconds=int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30")),
        sandbox_memory_mb=int(os.getenv("SANDBOX_MEMORY_MB", "256")),
        sandbox_cpu_seconds=int(os.getenv("SANDBOX_CPU_SECONDS", "20")),
        sandbox_output_limit=int(os.getenv("SANDBOX_OUTPUT_LIMIT", "200000")),
        sandbox_docker_image=os.getenv("SANDBOX_DOCKER_IMAGE", "python:3.11-alpine"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "180")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        agent_build_root=(base_dir / os.getenv("AGENT_BUILD_ROOT", "data/generated")).resolve(),
        agent_max_files=int(os.getenv("AGENT_MAX_FILES", "80")),
        agent_max_file_bytes=int(os.getenv("AGENT_MAX_FILE_BYTES", "300000")),
        agent_build_timeout_seconds=int(os.getenv("AGENT_BUILD_TIMEOUT_SECONDS", "600")),
        agent_build_docker_image=os.getenv("AGENT_BUILD_DOCKER_IMAGE", "agent-build:py311-node20"),
        deployment_public_host=os.getenv("DEPLOYMENT_PUBLIC_HOST", "localhost"),
        deployment_smoke_timeout_seconds=int(os.getenv("DEPLOYMENT_SMOKE_TIMEOUT_SECONDS", "45")),
        deployment_backend_memory_mb=int(os.getenv("DEPLOYMENT_BACKEND_MEMORY_MB", "512")),
        deployment_frontend_memory_mb=int(os.getenv("DEPLOYMENT_FRONTEND_MEMORY_MB", "256")),
        jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-this-secret-before-production"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "7")),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        queue_name=os.getenv("QUEUE_NAME", "agent-platform"),
        queue_fallback_threads=_as_bool(os.getenv("QUEUE_FALLBACK_THREADS"), True),
        run_db_migrations=_as_bool(os.getenv("RUN_DB_MIGRATIONS"), True),
        oidc_issuer=os.getenv("OIDC_ISSUER", "").rstrip("/"),
        oidc_client_id=os.getenv("OIDC_CLIENT_ID", ""),
        oidc_client_secret=os.getenv("OIDC_CLIENT_SECRET", ""),
        oidc_redirect_uri=os.getenv("OIDC_REDIRECT_URI", "http://localhost:4173/login/callback"),
        ldap_url=os.getenv("LDAP_URL", ""),
        ldap_base_dn=os.getenv("LDAP_BASE_DN", ""),
        ldap_bind_dn=os.getenv("LDAP_BIND_DN", ""),
        ldap_bind_password=os.getenv("LDAP_BIND_PASSWORD", ""),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        minio_bucket=os.getenv("MINIO_BUCKET", "agent-platform"),
        minio_secure=_as_bool(os.getenv("MINIO_SECURE"), False),
        git_remote_url=os.getenv("GIT_REMOTE_URL", ""),
        git_default_branch=os.getenv("GIT_DEFAULT_BRANCH", "main"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        notification_webhook_url=os.getenv("NOTIFICATION_WEBHOOK_URL", ""),
        agent_engine=os.getenv("AGENT_ENGINE", "deepagents").lower(),
        langgraph_checkpoint_db=(base_dir / os.getenv("LANGGRAPH_CHECKPOINT_DB", "data/langgraph_checkpoints.sqlite")).resolve(),
        generated_database_url=os.getenv("GENERATED_DATABASE_URL", ""),
        conversation_context_tokens=int(os.getenv("CONVERSATION_CONTEXT_TOKENS", "6000")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "") or os.getenv("LLM_MODEL", ""),
        conversation_history_min_messages=int(os.getenv("CONVERSATION_HISTORY_MIN_MESSAGES", "12")),
        generated_database_backup_dir=(base_dir / os.getenv("GENERATED_DATABASE_BACKUP_DIR", "data/generated-db-backups")).resolve(),
    )
