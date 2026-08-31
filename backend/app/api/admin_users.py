from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import audit, get_current_user, hash_password, require_platform_admin, require_super_admin
from app.core.errors import conflict, not_found
from app.database import get_db
from app.models import Project, ProjectMember, User
from app.schemas import AdminUserCreate, AdminUserCreatedResponse, AdminUserResponse, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["user-administration"], dependencies=[Depends(require_platform_admin)])


def _temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def user_response(db: Session, user: User) -> AdminUserResponse:
    owned_projects = db.scalar(select(func.count(Project.id)).where(Project.owner_id == user.id)) or 0
    project_count = (
        db.scalar(
            select(func.count(func.distinct(ProjectMember.project_id))).where(ProjectMember.user_id == user.id, ProjectMember.status == "active")
        )
        or 0
    ) + owned_projects
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        department=user.department,
        platform_role=user.platform_role,
        is_active=user.is_active,
        auth_source=user.auth_source,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        project_count=project_count,
        owned_projects=owned_projects,
    )


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db)) -> list[AdminUserResponse]:
    return [user_response(db, item) for item in db.scalars(select(User).order_by(User.created_at)).all()]


@router.post("/users", response_model=AdminUserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: AdminUserCreate, request: Request, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminUserCreatedResponse:
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise conflict("USER_EMAIL_INVALID", "企业邮箱格式不正确")
    if db.scalar(select(User).where(User.email == email)):
        raise conflict("USER_EXISTS", "该邮箱已存在平台用户")
    if payload.platform_role == "super_admin":
        require_super_admin(actor)
    temp_password = payload.initial_password or _temp_password()
    item = User(
        email=email,
        display_name=payload.display_name.strip(),
        department=payload.department.strip(),
        platform_role=payload.platform_role,
        password_hash=hash_password(temp_password),
        auth_source="local",
    )
    db.add(item)
    db.flush()
    audit(db, actor, "admin.user.create", resource_type="user", resource_id=item.id, metadata={"email": email, "role": payload.platform_role}, request=request)
    db.commit()
    db.refresh(item)
    return AdminUserCreatedResponse(user=user_response(db, item), temp_password=None if payload.initial_password else temp_password)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: str, payload: AdminUserUpdate, request: Request, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminUserResponse:
    item = db.get(User, user_id)
    if not item:
        raise not_found("平台用户", user_id)
    changes = payload.model_dump(exclude_unset=True)
    role_change = changes.get("platform_role")
    if role_change and (role_change == "super_admin" or item.platform_role == "super_admin"):
        require_super_admin(actor)
    if changes.get("is_active") is False:
        if item.id == actor.id:
            raise conflict("USER_SELF_DISABLE", "不能停用当前登录账号")
        if item.platform_role == "super_admin":
            require_super_admin(actor)
    if changes.get("is_active") is True and item.platform_role == "super_admin":
        require_super_admin(actor)
    if item.id == actor.id and role_change and role_change != "super_admin" and item.platform_role == "super_admin":
        raise conflict("USER_SELF_DEMOTE", "不能降低当前超级管理员账号的角色")
    new_password = changes.pop("new_password", None)
    if new_password:
        item.password_hash = hash_password(new_password)
        audit(db, actor, "admin.user.password_reset", resource_type="user", resource_id=item.id, request=request)
    for key, value in changes.items():
        setattr(item, key, value)
    audit(db, actor, "admin.user.update", resource_type="user", resource_id=item.id, metadata=dict(changes), request=request)
    db.commit()
    db.refresh(item)
    return user_response(db, item)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, request: Request, payload: dict | None = Body(default=None), actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除用户；拥有项目时可选择将其项目移交当前管理员后删除（reassign=true）。"""
    item = db.get(User, user_id)
    if not item:
        raise not_found("平台用户", user_id)
    if item.id == actor.id:
        raise conflict("USER_SELF_DELETE", "不能删除当前登录账号")
    if item.platform_role == "super_admin":
        raise conflict("USER_SUPER_ADMIN_PROTECTED", "超级管理员账号受保护，不能删除")
    owned = list(db.scalars(select(Project).where(Project.owner_id == item.id)).all())
    reassign = bool(payload and payload.get("reassign"))
    if owned and not reassign:
        raise conflict("USER_OWNS_PROJECTS", f"该用户仍拥有 {len(owned)} 个项目", projects=[p.name for p in owned][:10])
    if owned:
        for project in owned:
            project.owner_id = actor.id
            project.owner_name = actor.display_name
            audit(db, actor, "project.ownership.transfer", project_id=project.id, resource_type="project", resource_id=project.id, metadata={"fromUserId": item.id}, request=request)
    audit(db, actor, "admin.user.delete", resource_type="user", resource_id=item.id, metadata={"email": item.email, "reassignedProjects": len(owned)}, request=request)
    db.delete(item)
    db.commit()
    return None
