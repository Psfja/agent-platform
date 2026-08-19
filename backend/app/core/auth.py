from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database import get_db
from app.models import AuditLog, Project, ProjectMember, RefreshToken, User

bearer = HTTPBearer(auto_error=False)
PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_tokens(db: Session, user: User) -> tuple[str, str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(minutes=settings.access_token_minutes)
    refresh_exp = now + timedelta(days=settings.refresh_token_days)
    access = jwt.encode({"sub": user.id, "role": user.platform_role, "type": "access", "iat": now, "exp": access_exp, "jti": str(uuid.uuid4())}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    refresh_jti = str(uuid.uuid4())
    refresh = jwt.encode({"sub": user.id, "type": "refresh", "iat": now, "exp": refresh_exp, "jti": refresh_jti}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    db.add(RefreshToken(user_id=user.id, jti_hash=hashlib.sha256(refresh_jti.encode()).hexdigest(), expires_at=refresh_exp))
    return access, refresh, settings.access_token_minutes * 60


def decode_token(token: str, expected_type: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "TOKEN_EXPIRED", "登录凭据已过期") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "TOKEN_INVALID", "登录凭据无效") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise AppError(401, "TOKEN_INVALID", "登录凭据类型无效")
    return payload


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else request.query_params.get("access_token")
    if not token:
        raise AppError(401, "AUTH_REQUIRED", "请先登录", {"loginPath": "/login"})
    payload = decode_token(token, "access")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise AppError(401, "USER_DISABLED", "用户不存在或已停用")
    return user


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if user.platform_role not in {"super_admin", "platform_admin"}:
        raise AppError(403, "PLATFORM_ADMIN_REQUIRED", "需要平台管理员权限")
    return user


def enforce_project_access(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    project_id = request.path_params.get("project_id")
    if not project_id:
        return user
    if user.platform_role in {"super_admin", "platform_admin"}:
        return user
    project = db.get(Project, project_id)
    if not project:
        return user  # route-level 404 remains authoritative
    if project.owner_id == user.id:
        return user
    membership = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id, ProjectMember.status == "active"))
    if not membership:
        raise AppError(403, "PROJECT_ACCESS_DENIED", "你没有该项目的访问权限")
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return user
    path = request.url.path
    owner_only = any(marker in path for marker in ["/application-deployments", "/versions/", "/members"])
    if owner_only:
        raise AppError(403, "PROJECT_OWNER_REQUIRED", "该操作仅项目所有者可执行")
    if membership.role != "co_manager":
        raise AppError(403, "PROJECT_WRITE_DENIED", "当前项目角色没有编辑或干预权限")
    return user


def audit(db: Session, user: User | None, action: str, *, project_id: str | None = None, resource_type: str = "", resource_id: str = "", metadata: dict | None = None, request: Request | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        project_id=project_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        ip_address=request.client.host if request and request.client else "",
    ))
