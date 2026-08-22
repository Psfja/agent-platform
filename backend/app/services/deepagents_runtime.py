from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AgentType
from app.services.agent_runtime import agent_runtime


@tool
def request_database_migration(description: str, destructive: bool = False) -> str:
    """Request human approval before applying a database migration."""
    return f"Database migration approved: {description}; destructive={destructive}"


@tool
def request_production_deployment(version: str, summary: str) -> str:
    """Request human approval before deploying a version to production."""
    return f"Production deployment approved: {version}; {summary}"


def build_langgraph_checkpointer(settings: Any):
    """PostgreSQL 部署自动切换 PostgresSaver；不可用时回退 SQLite 并给出提示。"""
    import logging

    logger = logging.getLogger("agent-platform")
    if settings.database_url.startswith("postgresql"):
        try:
            import psycopg
            from langgraph.checkpoint.postgres import PostgresSaver

            dsn = settings.database_url.replace("postgresql+psycopg", "postgresql")
            connection = psycopg.connect(dsn, autocommit=True)
            saver = PostgresSaver(connection)
            saver.setup()
            logger.info("LangGraph checkpointer: PostgreSQL")
            return saver
        except Exception as exc:  # noqa: BLE001
            logger.warning("PostgreSQL checkpointer 不可用（%s），回退 SQLite", exc)
    settings.langgraph_checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.langgraph_checkpoint_db, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    logger.info("LangGraph checkpointer: SQLite（%s）", settings.langgraph_checkpoint_db)
    return saver


@dataclass(slots=True)
class NativeAgentOutcome:
    status: str
    result: dict[str, Any]
    interrupt: dict[str, Any] | None = None


class DeepAgentsRuntime:
    def __init__(self) -> None:
        self.checkpointer = build_langgraph_checkpointer(get_settings())
        self.lock = threading.RLock()

    def invoke(self, db: Session, project_id: str, build_id: str, workspace: Path, requirement: str, resume_decision: dict | None = None) -> NativeAgentOutcome:
        settings = get_settings()
        model = ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0.05, timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
        context = agent_runtime.build_context(db, project_id, "project-manager", requirement)
        memory_path = workspace / "AGENTS.md"
        memory_path.write_text(f"# Persistent project context\n\n{context['memory_prompt']}\n", encoding="utf-8")
        subagents = self._subagents(db, model, settings)
        agent = create_deep_agent(
            name="software-delivery-supervisor",
            model=model,
            tools=[request_database_migration, request_production_deployment],
            system_prompt=(
                "You lead a software delivery team. You MUST delegate architecture, backend, frontend, review, and testing work to the specialized subagents using the task tool. "
                "Work only inside /backend, /frontend, and /docs. Produce a complete Vue 3 + FastAPI application. Run tests and repair failures. "
                "Before any destructive database migration call request_database_migration. Before production deployment call request_production_deployment."
            ),
            subagents=subagents,
            skills=[str(path) for path in settings.skill_directories],
            memory=[str(memory_path)],
            backend=FilesystemBackend(root_dir=workspace, virtual_mode=True, max_file_size_mb=2),
            interrupt_on={
                "request_database_migration": {"allowed_decisions": ["approve", "edit", "reject"]},
                "request_production_deployment": {"allowed_decisions": ["approve", "edit", "reject"]},
            },
            checkpointer=self.checkpointer,
        )
        config = {"configurable": {"thread_id": build_id}}
        with self.lock:
            if resume_decision:
                decision_type = resume_decision.get("decision", "reject")
                if decision_type == "approve": decision = {"type": "approve"}
                elif decision_type == "edit": decision = {"type": "edit", "edited_action": resume_decision.get("editedAction", {})}
                else: decision = {"type": "reject", "message": resume_decision.get("reason", "Rejected by reviewer")}
                result = agent.invoke(Command(resume={"decisions": [decision]}), config=config)
            else:
                result = agent.invoke({"messages": [{"role": "user", "content": f"Build this application and verify it with tests. Requirement:\n{requirement}"}]}, config=config)
        interrupts = result.get("__interrupt__", []) if isinstance(result, dict) else []
        if interrupts:
            value = getattr(interrupts[0], "value", interrupts[0])
            return NativeAgentOutcome("waiting_approval", result, value if isinstance(value, dict) else {"value": str(value)})
        return NativeAgentOutcome("completed", result if isinstance(result, dict) else {"result": str(result)})

    @staticmethod
    def _subagents(db: Session, model: ChatOpenAI, settings) -> list[dict]:
        rows = db.scalars(select(AgentType).where(AgentType.is_active.is_(True))).all()
        wanted = {"architect", "backend-developer", "frontend-developer", "code-reviewer", "test-engineer", "deployment-engineer"}
        result = []
        for item in rows:
            if item.name not in wanted: continue
            skill_paths = []
            for root in settings.skill_directories:
                for skill in item.skills or []:
                    path = root / skill
                    if path.is_dir(): skill_paths.append(str(path))
            result.append({"name": item.name, "description": item.description, "system_prompt": item.system_prompt, "model": model, "skills": skill_paths})
        return result


native_deepagents_runtime = DeepAgentsRuntime()
