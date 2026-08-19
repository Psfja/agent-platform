from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.database import get_db
from app.models import ProjectAttachment, ProjectDocument, RequirementClarification, RequirementVersion, User
from app.schemas import ClarificationAnswer, ClarificationCreate, DocumentCreate, DocumentResponse, RequirementCreate, RequirementResponse
from app.services.integrations import artifact_storage

router = APIRouter(tags=["requirements-and-documents"])


def requirement_response(item: RequirementVersion) -> RequirementResponse:
    return RequirementResponse(id=item.id, project_id=item.project_id, version=item.version, title=item.title, content_markdown=item.content_markdown, structured_data=item.structured_data or {}, status=item.status, change_summary=item.change_summary, created_by=item.created_by, created_at=item.created_at)


def document_response(item: ProjectDocument) -> DocumentResponse:
    return DocumentResponse(id=item.id, project_id=item.project_id, document_type=item.document_type, version=item.version, title=item.title, content_markdown=item.content_markdown, source_build_id=item.source_build_id, metadata=item.metadata_json or {}, created_by=item.created_by, created_at=item.created_at, updated_at=item.updated_at)


@router.get("/projects/{project_id}/requirements", response_model=list[RequirementResponse])
def list_requirements(project_id: str, db: Session = Depends(get_db)) -> list[RequirementResponse]:
    get_project_or_404(db, project_id)
    return [requirement_response(item) for item in db.scalars(select(RequirementVersion).where(RequirementVersion.project_id == project_id).order_by(RequirementVersion.version.desc())).all()]


@router.post("/projects/{project_id}/requirements", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
def save_requirement(project_id: str, payload: RequirementCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RequirementResponse:
    project = get_project_or_404(db, project_id)
    version = (db.scalar(select(func.max(RequirementVersion.version)).where(RequirementVersion.project_id == project_id)) or 0) + 1
    item = RequirementVersion(project_id=project_id, version=version, title=payload.title, content_markdown=payload.content_markdown, structured_data=payload.structured_data, status=payload.status, change_summary=payload.change_summary, created_by=user.id)
    db.add(item)
    if payload.status == "confirmed": project.description = payload.structured_data.get("summary", project.description)
    db.commit(); db.refresh(item); return requirement_response(item)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents(project_id: str, db: Session = Depends(get_db)) -> list[DocumentResponse]:
    get_project_or_404(db, project_id)
    return [document_response(item) for item in db.scalars(select(ProjectDocument).where(ProjectDocument.project_id == project_id).order_by(ProjectDocument.document_type, ProjectDocument.version.desc())).all()]


@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def save_document(project_id: str, payload: DocumentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DocumentResponse:
    get_project_or_404(db, project_id)
    version = (db.scalar(select(func.max(ProjectDocument.version)).where(ProjectDocument.project_id == project_id, ProjectDocument.document_type == payload.document_type)) or 0) + 1
    item = ProjectDocument(project_id=project_id, document_type=payload.document_type, version=version, title=payload.title, content_markdown=payload.content_markdown, source_build_id=payload.source_build_id, metadata_json=payload.metadata, created_by=user.id)
    db.add(item); db.commit(); db.refresh(item); return document_response(item)


@router.post("/projects/{project_id}/attachments", status_code=status.HTTP_201_CREATED)
def upload_attachment(project_id: str, user: User = Depends(get_current_user), file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    get_project_or_404(db, project_id)
    settings = get_settings(); upload_dir = settings.base_dir / "data" / "uploads" / project_id; upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "attachment.bin").name
    target = upload_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{safe_name}"
    digest = hashlib.sha256(); size = 0
    with target.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > 20 * 1024 * 1024: target.unlink(missing_ok=True); raise AppError(413, "ATTACHMENT_TOO_LARGE", "附件不能超过 20MB")
            digest.update(chunk); output.write(chunk)
    extracted = extract_text(target, file.content_type or "")
    storage = artifact_storage.upload(target, f"projects/{project_id}/attachments/{target.name}")
    item = ProjectAttachment(project_id=project_id, filename=safe_name, content_type=file.content_type or "application/octet-stream", size_bytes=size, storage_provider=storage["provider"], storage_path=storage.get("uri", storage.get("path", str(target))), checksum=digest.hexdigest(), extracted_text=extracted[:200000], uploaded_by=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "filename": item.filename, "contentType": item.content_type, "sizeBytes": item.size_bytes, "storageProvider": item.storage_provider, "checksum": item.checksum, "extractedTextLength": len(item.extracted_text), "createdAt": item.created_at}


@router.get("/projects/{project_id}/attachments")
def list_attachments(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    get_project_or_404(db, project_id)
    rows = db.scalars(select(ProjectAttachment).where(ProjectAttachment.project_id == project_id).order_by(ProjectAttachment.created_at.desc())).all()
    return [{"id": i.id, "filename": i.filename, "contentType": i.content_type, "sizeBytes": i.size_bytes, "storageProvider": i.storage_provider, "checksum": i.checksum, "extractedText": i.extracted_text, "createdAt": i.created_at} for i in rows]


@router.post("/projects/{project_id}/clarifications", status_code=status.HTTP_201_CREATED)
def create_clarification(project_id: str, payload: ClarificationCreate, db: Session = Depends(get_db)) -> dict:
    get_project_or_404(db, project_id); item = RequirementClarification(project_id=project_id, requirement_version_id=payload.requirement_version_id, question=payload.question); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "question": item.question, "answer": item.answer, "status": item.status, "createdAt": item.created_at}


@router.get("/projects/{project_id}/clarifications")
def list_clarifications(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    get_project_or_404(db, project_id); rows=db.scalars(select(RequirementClarification).where(RequirementClarification.project_id==project_id).order_by(RequirementClarification.created_at)).all()
    return [{"id": i.id, "question": i.question, "answer": i.answer, "status": i.status, "createdAt": i.created_at, "answeredAt": i.answered_at} for i in rows]


@router.post("/projects/{project_id}/clarifications/{clarification_id}/answer")
def answer_clarification(project_id: str, clarification_id: str, payload: ClarificationAnswer, db: Session = Depends(get_db)) -> dict:
    item=db.scalar(select(RequirementClarification).where(RequirementClarification.id==clarification_id,RequirementClarification.project_id==project_id))
    if not item: raise not_found("澄清问题",clarification_id)
    item.answer=payload.answer;item.status="answered";item.answered_at=datetime.now(timezone.utc);db.commit()
    return {"id":item.id,"status":item.status,"answer":item.answer,"answeredAt":item.answered_at}


def extract_text(path: Path, content_type: str) -> str:
    try:
        if content_type == "application/pdf" or path.suffix.lower() == ".pdf":
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages[:100])
        if path.suffix.lower() in {".txt", ".md", ".json", ".csv", ".yaml", ".yml"}:
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return ""
