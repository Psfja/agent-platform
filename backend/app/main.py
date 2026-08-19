from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import get_settings
from app.database import SessionLocal, create_schema
from app.services.agent_builder import recover_stale_builds
from app.services.application_deployer import recover_stale_deployments
from app.services.migrations import run_platform_migrations
from app.services.seed import seed_demo_data, seed_runtime_data
from app.services.skill_loader import skill_registry
from app.services.task_queue import persistent_queue
from app.services.monitoring import prometheus_payload

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.app_env == "production" and settings.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be changed before production startup")
    if settings.run_db_migrations:
        run_platform_migrations()
    else:
        create_schema()
    skill_registry.reload()
    with SessionLocal() as db:
        if settings.seed_demo_data:
            seed_demo_data(db)
            seed_runtime_data(db)
        if persistent_queue.available:
            persistent_queue.requeue_orphans()
        else:
            recover_stale_builds(db)
            recover_stale_deployments(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="企业智能体平台核心闭环 API：项目、任务、干预、增量迭代、版本与 SSE。",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{time.perf_counter() - started:.4f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "details": exc.errors()}},
    )


@app.get("/", tags=["system"])
def root():
    return {"name": settings.app_name, "status": "running", "docs": "/docs", "api": settings.api_prefix}


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "agent-platform-api", "version": "0.1.0", "environment": settings.app_env}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=prometheus_payload(), media_type=CONTENT_TYPE_LATEST)


app.include_router(api_router, prefix=settings.api_prefix)
