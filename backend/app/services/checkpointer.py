from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentCheckpoint


class SQLAlchemyLangGraphCheckpointer:
    """Durable stage checkpoint store using LangGraph-style thread_id/config semantics."""

    def save(self, db: Session, thread_id: str, run_id: str, stage: str, state: dict) -> AgentCheckpoint:
        version = (db.scalar(select(func.max(AgentCheckpoint.version)).where(AgentCheckpoint.thread_id == thread_id)) or 0) + 1
        item = AgentCheckpoint(thread_id=thread_id, run_id=run_id, version=version, stage=stage, state=state)
        db.add(item); db.flush(); return item

    def latest(self, db: Session, thread_id: str) -> AgentCheckpoint | None:
        return db.scalar(select(AgentCheckpoint).where(AgentCheckpoint.thread_id == thread_id).order_by(AgentCheckpoint.version.desc()).limit(1))

    def history(self, db: Session, thread_id: str, limit: int = 50) -> list[AgentCheckpoint]:
        return list(db.scalars(select(AgentCheckpoint).where(AgentCheckpoint.thread_id == thread_id).order_by(AgentCheckpoint.version.desc()).limit(limit)).all())

    # LangGraph-compatible config shape for future BaseCheckpointSaver adapter.
    def put(self, db: Session, config: dict, checkpoint: dict, metadata: dict | None = None) -> dict:
        configurable = config.get("configurable", {})
        thread_id = configurable["thread_id"]
        run_id = configurable.get("run_id", thread_id)
        stage = (metadata or {}).get("stage", checkpoint.get("stage", "unknown"))
        item = self.save(db, thread_id, run_id, stage, checkpoint)
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": item.id, "checkpoint_version": item.version}}

    def get(self, db: Session, config: dict) -> dict | None:
        thread_id = config.get("configurable", {}).get("thread_id")
        item = self.latest(db, thread_id) if thread_id else None
        return item.state if item else None


checkpoint_store = SQLAlchemyLangGraphCheckpointer()
