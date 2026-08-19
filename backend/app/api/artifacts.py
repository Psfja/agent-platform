from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import Artifact
from app.schemas import ArtifactResponse
from app.serializers import artifact_response

router = APIRouter(tags=["artifacts"])


@router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactResponse])
def list_artifacts(
    project_id: str,
    artifact_type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
) -> list[ArtifactResponse]:
    get_project_or_404(db, project_id)
    query = select(Artifact).where(Artifact.project_id == project_id)
    if artifact_type:
        query = query.where(Artifact.artifact_type == artifact_type)
    rows = db.scalars(query.order_by(Artifact.created_at.desc())).all()
    return [artifact_response(item) for item in rows]
