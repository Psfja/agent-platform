from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AgentMemory
from app.schemas import MemoryCreate

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")


class MemoryService:
    @staticmethod
    def create(db: Session, project_id: str, payload: MemoryCreate) -> AgentMemory:
        item = AgentMemory(
            project_id=project_id,
            agent_key=payload.agent_key,
            scope=payload.scope,
            memory_type=payload.memory_type,
            key=payload.key,
            content=payload.content,
            importance=payload.importance,
            tags=payload.tags,
            metadata_json=payload.metadata,
            expires_at=payload.expires_at,
        )
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def retrieve(
        db: Session,
        project_id: str,
        agent_key: str | None = None,
        query: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
        touch: bool = False,
    ) -> list[AgentMemory]:
        now = datetime.now(timezone.utc)
        statement = select(AgentMemory).where(
            AgentMemory.project_id == project_id,
            or_(AgentMemory.expires_at.is_(None), AgentMemory.expires_at > now),
        )
        if agent_key:
            statement = statement.where(or_(AgentMemory.agent_key == agent_key, AgentMemory.scope == "project"))
        if memory_type:
            statement = statement.where(AgentMemory.memory_type == memory_type)
        candidates = list(db.scalars(statement.order_by(AgentMemory.importance.desc(), AgentMemory.updated_at.desc()).limit(200)).all())
        if query:
            query_tokens = set(_TOKEN_RE.findall(query.lower()))
            def score(item: AgentMemory) -> tuple[float, datetime]:
                haystack = f"{item.key} {item.content} {' '.join(item.tags or [])}".lower()
                overlap = sum(1 for token in query_tokens if token in haystack)
                return (overlap * 2 + item.importance, item.updated_at)
            candidates.sort(key=score, reverse=True)
            if query_tokens:
                matching = [item for item in candidates if any(token in f"{item.key} {item.content} {' '.join(item.tags or [])}".lower() for token in query_tokens)]
                candidates = matching or candidates
        selected = candidates[:limit]
        if touch and selected:
            for item in selected:
                item.access_count += 1
                item.last_accessed_at = now
            db.flush()
        return selected

    @staticmethod
    def build_prompt(memories: list[AgentMemory]) -> str:
        if not memories:
            return "No persisted project memory is available."
        lines = ["## Relevant persistent memory"]
        for item in memories:
            tags = f" tags={','.join(item.tags)}" if item.tags else ""
            lines.append(f"- [{item.memory_type}/{item.key}]{tags}: {item.content}")
        lines.append("Use these memories as project context. New human instructions take priority.")
        return "\n".join(lines)


memory_service = MemoryService()
