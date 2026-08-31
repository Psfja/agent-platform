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

    @classmethod
    def retrieve(
        cls,
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
        if query and selected:
            selected = cls._semantic_rerank(selected, query)
            selected = selected[:limit]
        if touch and selected:
            for item in selected:
                item.access_count += 1
                item.last_accessed_at = now
            db.flush()
        return selected

    _embedding_cache: dict[str, list[float]] = {}

    @classmethod
    def _cosine(cls, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm_l = sum(a * a for a in left) ** 0.5
        norm_r = sum(b * b for b in right) ** 0.5
        return dot / (norm_l * norm_r) if norm_l and norm_r else 0.0

    @classmethod
    def _semantic_rerank(cls, candidates: list[AgentMemory], query: str) -> list[AgentMemory]:
        """语义向量重排：embedding 可用时按 关键词得分×0.5 + 余弦相似度×0.5 混合排序；任何失败保持原顺序。"""
        try:
            from app.services.llm_client import OpenAICompatibleClient

            client = OpenAICompatibleClient()
            query_vector = client.embed_query(query)
            if query_vector is None:
                return candidates
            query_tokens = set(_TOKEN_RE.findall(query.lower()))
            ranked: list[tuple[float, AgentMemory]] = []
            for item in candidates:
                haystack = f"{item.key} {item.content} {' '.join(item.tags or [])}".lower()
                keyword_score = sum(1 for token in query_tokens if token in haystack) * 2 + item.importance
                cache_key = haystack
                vector = cls._embedding_cache.get(cache_key)
                if vector is None:
                    vector = client.embed_query(item.content[:8000])
                    if vector is not None and len(cls._embedding_cache) < 512:
                        cls._embedding_cache[cache_key] = vector
                cosine = cls._cosine(query_vector, vector or [])
                ranked.append((keyword_score * 0.5 + cosine * 0.5, item))
            ranked.sort(key=lambda pair: (-pair[0], -pair[1].importance))
            return [item for _, item in ranked]
        except Exception:  # noqa: BLE001 —— 语义增强失败降级为关键词排序
            return candidates

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
