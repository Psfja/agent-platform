from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database import SessionLocal
from app.models import AgentType, Conversation, ConversationInterrupt, ConversationMessage
from app.services.agent_runtime import agent_runtime
from app.services.conversation import _generate_title, conversation_response, sse_event
from app.services.memory import memory_service
from app.services.sandbox import sandbox_manager


@tool
def run_python_in_sandbox(code: str, stdin: str = "") -> str:
    """在隔离沙箱中执行 Python 代码（用于计算、验证假设、生成小工具或测试片段）。

    Args:
        code: 需要执行的完整 Python 源码。
        stdin: 可选的标准输入。

    Returns:
        执行结果 JSON：status、exitCode、stdout、stderr 与资源消耗。
    """
    run_id = f"conversation-{uuid.uuid4().hex[:12]}"
    result = sandbox_manager.execute_python(run_id, code, stdin=stdin, timeout_seconds=30)
    return json.dumps(
        {
            "status": result.status,
            "exitCode": result.exit_code,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "elapsedMs": result.elapsed_ms,
        },
        ensure_ascii=False,
    )


@tool
def request_production_deployment(version: str, summary: str) -> str:
    """申请将当前成果部署到生产环境（需要人工审批）。"""
    return f"Production deployment requested: {version}; {summary}"


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


class ConversationAgentRuntime:
    """每个对话一个 DeepAgents 智能体：FilesystemBackend 工作区 + TodoList +
    平台子智能体委派（task tool）+ 沙箱 Python 工具 + Skills + 长期记忆 + HITL。"""

    session_factory = SessionLocal
    _lock = threading.RLock()

    def workspace_dir(self, project_id: str) -> Path:
        settings = get_settings()
        return (settings.base_dir / "data" / "conversation-workspaces" / project_id).resolve()

    def workspace_files(self, project_id: str) -> list[dict[str, Any]]:
        root = self.workspace_dir(project_id)
        if not root.is_dir():
            return []
        entries: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "AGENTS.md" and ".git" not in path.parts:
                rel = path.relative_to(root).as_posix()
                entries.append({"path": rel, "size": path.stat().st_size})
        return entries[:500]

    def _checkpointer(self):
        from app.services.deepagents_runtime import build_langgraph_checkpointer

        return build_langgraph_checkpointer(get_settings())

    def _model(self):
        settings = get_settings()
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.2,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def _subagents(self, db: Session, model: ChatOpenAI) -> list[dict[str, Any]]:
        settings = get_settings()
        rows = db.scalars(select(AgentType).where(AgentType.is_active.is_(True))).all()
        wanted = {"architect", "backend-developer", "frontend-developer", "code-reviewer", "test-engineer", "deployment-engineer"}
        result: list[dict[str, Any]] = []
        for item in rows:
            if item.name not in wanted:
                continue
            skill_paths = []
            for root in settings.skill_directories:
                for skill in item.skills or []:
                    path = root / skill
                    if path.is_dir():
                        skill_paths.append(str(path))
            result.append({
                "name": item.name,
                "description": item.description,
                "system_prompt": item.system_prompt,
                "model": model,
                "skills": skill_paths,
            })
        return result

    def build_agent(self, db: Session, conversation: Conversation, agent: AgentType):
        settings = get_settings()
        model = self._model()
        workspace = self.workspace_dir(conversation.project_id)
        workspace.mkdir(parents=True, exist_ok=True)
        memory = agent_runtime.build_context(db, conversation.project_id, conversation.agent_key, None)
        memory_file = workspace / "AGENTS.md"
        memory_file.write_text(f"# Persistent project context\n\n{memory['memory_prompt']}\n", encoding="utf-8")
        skill_paths = []
        for root in settings.skill_directories:
            for skill in agent.skills or []:
                path = root / skill
                if path.is_dir():
                    skill_paths.append(str(path))
        deep_agent = create_deep_agent(
            name=f"conversation-{conversation.id[:8]}",
            model=model,
            tools=[run_python_in_sandbox, request_production_deployment],
            system_prompt=(
                f"{agent.system_prompt}\n\n"
                "You are helping the user inside an enterprise agent platform conversation. "
                "You have a real filesystem workspace under / (virtual_mode) — use ls/read_file/write_file/edit_file to create or modify files. "
                "You can execute Python in an isolated sandbox with run_python_in_sandbox. "
                "Delegate larger engineering tasks to the specialized subagents via the task tool. "
                "Use the todo list for multi-step work. "
                "Before requesting a production deployment call request_production_deployment and wait for human approval. "
                "Summarize what you did when finished, including files changed and sandbox results."
            ),
            subagents=self._subagents(db, model),
            skills=skill_paths,
            memory=[str(memory_file)],
            backend=FilesystemBackend(root_dir=workspace, virtual_mode=True, max_file_size_mb=2),
            interrupt_on={
                "request_production_deployment": {"allowed_decisions": ["approve", "edit", "reject"]},
            },
            checkpointer=self._checkpointer(),
        )
        return deep_agent, {"configurable": {"thread_id": conversation.id}}

    def _pending_interrupts(self, deep_agent: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            state = deep_agent.get_state(config)
        except Exception:  # noqa: BLE001
            return []
        found: list[dict[str, Any]] = []
        for task in getattr(state, "tasks", None) or []:
            for interrupt in getattr(task, "interrupts", None) or []:
                value = getattr(interrupt, "value", None)
                payload = value if isinstance(value, dict) else {"value": str(value)}
                tool_name = ""
                for key in ("name", "tool", "tool_name"):
                    if isinstance(payload, dict) and payload.get(key):
                        tool_name = str(payload[key])
                        break
                found.append({"toolName": tool_name or "pending_approval", "payload": payload})
        return found

    def stream(
        self,
        db: Session,
        project_id: str,
        conversation: Conversation,
        agent: AgentType,
        content: str,
    ) -> Iterator[str]:
        """SSE 流：meta → delta* → (interrupt) → done / error。"""
        if not get_settings().llm_api_key:
            yield sse_event({"type": "error", "code": "LLM_NOT_CONFIGURED", "message": "真实 Agent 需要配置 LLM_API_KEY", "status": 503})
            return
        now = datetime.now(timezone.utc)
        user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=content)
        db.add(user_message)
        db.flush()
        context = agent_runtime.build_context(db, conversation.project_id, conversation.agent_key, content)
        yield sse_event({"type": "meta", "context": {
            "memoriesRecalled": len(context["memories"]),
            "skillsLoaded": len(context["skills"]),
            "mode": "agent",
        }})

        deep_agent, config = self.build_agent(db, conversation, agent)
        chunks: list[str] = []
        interrupt: dict[str, Any] | None = None
        try:
            with self._lock:
                for message_chunk, _meta in deep_agent.stream(
                    {"messages": [{"role": "user", "content": content}]},
                    config,
                    stream_mode="messages",
                ):
                    text = _message_content(message_chunk)
                    if text:
                        chunks.append(text)
                        yield sse_event({"type": "delta", "content": text})
            pending = self._pending_interrupts(deep_agent, config)
            if pending:
                interrupt = pending[0]
        except AppError as exc:
            db.rollback()
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            yield sse_event({"type": "error", "code": detail.get("code", "AGENT_FAILED"), "message": detail.get("message", str(exc)), "status": exc.status_code})
            return
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            yield sse_event({"type": "error", "code": "AGENT_FAILED", "message": f"智能体执行失败：{exc}", "status": 502})
            return

        reply = "".join(chunks).strip()
        new_title: str | None = None
        assistant_message: ConversationMessage | None = None
        if reply:
            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=reply,
                metadata_json={"mode": "agent", "model": agent.model, "memoriesUsed": [m.id for m in context["memories"]]},
            )
            db.add(assistant_message)
            conversation.last_message_at = now
            conversation.updated_at = now
        if conversation.title == "新对话":
            new_title = _generate_title(db, conversation, [user_message], content, reply or "（等待人工审批）")
            conversation.title = new_title
            yield sse_event({"type": "title", "title": new_title})
        if interrupt:
            row = ConversationInterrupt(
                conversation_id=conversation.id,
                tool_name=interrupt.get("toolName", "pending_approval"),
                payload_json=interrupt.get("payload", {}),
                status="pending",
            )
            db.add(row)
            db.flush()
            yield sse_event({"type": "interrupt", "interruptId": row.id, "toolName": row.tool_name, "payload": row.payload_json})
        db.commit()
        db.refresh(conversation)
        yield sse_event({
            "type": "done",
            "conversation": conversation_response(db, conversation),
            "assistantMessage": {
                "id": assistant_message.id,
                "role": assistant_message.role,
                "content": assistant_message.content,
                "metadata": assistant_message.metadata_json or {},
                "created_at": assistant_message.created_at,
            } if assistant_message else None,
            "title": new_title,
            "interrupt": interrupt,
        })

    def decide(
        self,
        db: Session,
        conversation: Conversation,
        agent: AgentType,
        interrupt: ConversationInterrupt,
        decision: str,
        reason: str,
        edited_action: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """人工审批：approve / edit / reject 后通过 Command(resume=...) 恢复 Agent 并返回最终回复。"""
        if not get_settings().llm_api_key:
            raise AppError(503, "LLM_NOT_CONFIGURED", "真实 Agent 需要配置 LLM_API_KEY")
        deep_agent, config = self.build_agent(db, conversation, agent)
        if decision == "approve":
            resume = {"type": "approve"}
        elif decision == "edit":
            resume = {"type": "edit", "edited_action": edited_action or {}}
        else:
            resume = {"type": "reject", "message": reason or "Rejected by reviewer"}
        with self._lock:
            result = deep_agent.invoke(Command(resume={"decisions": [resume]}), config=config)
        messages = result.get("messages", []) if isinstance(result, dict) else []
        reply = ""
        for message in reversed(messages):
            if getattr(message, "type", None) in (None, "ai") and _message_content(message):
                reply = _message_content(message)
                break
        now = datetime.now(timezone.utc)
        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=reply or f"已{ {'approve': '批准', 'edit': '修改后批准', 'reject': '驳回'}[decision] }人工审批意见，Agent 已继续执行。",
            metadata_json={"mode": "agent", "decision": decision},
        )
        db.add(assistant_message)
        interrupt.status = "decided"
        interrupt.decision = decision
        interrupt.reason = reason[:2000]
        interrupt.decided_at = now
        conversation.last_message_at = now
        conversation.updated_at = now
        db.commit()
        db.refresh(conversation)
        return {
            "conversation": conversation_response(db, conversation),
            "assistantMessage": {
                "id": assistant_message.id,
                "role": assistant_message.role,
                "content": assistant_message.content,
                "metadata": assistant_message.metadata_json or {},
                "created_at": assistant_message.created_at,
            },
        }


conversation_agent_runtime = ConversationAgentRuntime()
