from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.core.auth import audit, get_current_user
from app.core.errors import conflict, not_found
from app.database import get_db
from app.models import ProjectMember, User
from app.schemas import ProjectMemberCreate, ProjectMemberResponse

router = APIRouter(tags=["project-members"])


def member_response(item: ProjectMember, user: User) -> ProjectMemberResponse:
    return ProjectMemberResponse(id=item.id, user_id=user.id, email=user.email, display_name=user.display_name, department=user.department, role=item.role, status=item.status, joined_at=item.joined_at)


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberResponse])
def list_project_members(project_id: str, db: Session = Depends(get_db)) -> list[ProjectMemberResponse]:
    project = get_project_or_404(db, project_id)
    rows = db.execute(select(ProjectMember, User).join(User, User.id == ProjectMember.user_id).where(ProjectMember.project_id == project_id, ProjectMember.status == "active")).all()
    result = [member_response(member, user) for member, user in rows]
    owner = db.get(User, project.owner_id)
    if owner and not any(item.user_id == owner.id for item in result):
        result.insert(0, ProjectMemberResponse(id=f"owner-{owner.id}", user_id=owner.id, email=owner.email, display_name=owner.display_name, department=owner.department, role="owner", status="active", joined_at=project.created_at))
    return result


@router.post("/projects/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_project_member(project_id: str, payload: ProjectMemberCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectMemberResponse:
    get_project_or_404(db, project_id)
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user:
        raise not_found("用户", payload.email)
    existing = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id))
    if existing and existing.status == "active":
        raise conflict("MEMBER_ALREADY_EXISTS", "用户已经是项目成员")
    if existing:
        existing.status, existing.role, existing.invited_by = "active", payload.role, current_user.id
        item = existing
    else:
        item = ProjectMember(project_id=project_id, user_id=user.id, role=payload.role, invited_by=current_user.id, status="active")
        db.add(item)
    db.flush()
    audit(db, current_user, "project.member.add", project_id=project_id, resource_type="user", resource_id=user.id, metadata={"role": payload.role}, request=request)
    db.commit(); db.refresh(item)
    return member_response(item, user)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(project_id: str, user_id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))
    if not item:
        raise not_found("项目成员", user_id)
    item.status = "removed"
    audit(db, current_user, "project.member.remove", project_id=project_id, resource_type="user", resource_id=user_id, request=request)
    db.commit()
    return None
