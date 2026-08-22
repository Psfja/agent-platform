from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import AgentType, Conversation, ConversationMessage
from app.schemas import MemoryCreate
from app.schemas import to_camel
from app.services.llm_client import ChatModel, OpenAICompatibleClient, estimate_tokens
from app.services.memory import memory_service
from app.services.skill_loader import skill_registry

conversation_client_factory: Callable[[str], ChatModel] = lambda model: OpenAICompatibleClient(model=model)


def _message_dict(item: ConversationMessage) -> dict[str, Any]:
    return {
        "id": item.id,
        "role": item.role,
        "content": item.content,
        "metadata": item.metadata_json or {},
        "created_at": item.created_at,
    }


def conversation_response(db: Session, item: Conversation) -> dict[str, Any]:
    count = db.scalar(select(func.count(ConversationMessage.id)).where(ConversationMessage.conversation_id == item.id)) or 0
    return {
        "id": item.id,
        "project_id": item.project_id,
        "agent_key": item.agent_key,
        "title": item.title,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "last_message_at": item.last_message_at,
        "message_count": count,
    }


def build_chat_context(
    db: Session,
    conversation: Conversation,
    agent: AgentType,
    history: list[ConversationMessage],
    query: str,
) -> dict[str, Any]:
    """组装对话上下文：系统提示词 + 长期记忆召回 + Skills 指令 + 裁剪后的历史。"""
    settings = get_settings()
    # 1) 长期记忆：按项目/Agent/查询相关性召回
    memories = memory_service.retrieve(
        db, project_id=conversation.project_id, agent_key=conversation.agent_key,
        query=query, limit=8, touch=True,
    )
    memory_prompt = memory_service.build_prompt(memories)
    # 2) 该智能体装配的 Skills 指令
    skills = [s for s in skill_registry.list(agent_key=conversation.agent_key)]
    skill_lines = ["## Loaded skills"]
    for skill in skills:
        skill_lines.append(f"### {skill.display_name} ({skill.name}@{skill.version})\n{skill.instructions}")
    skill_prompt = "\n\n".join(skill_lines) if skills else "No skills are loaded for this agent type."

    # 3) 历史裁剪：先保底保留最近 N 条，再在 Token 预算内尽量纳入更早消息
    budget = settings.conversation_context_tokens
    min_messages = settings.conversation_history_min_messages
    base_tokens = estimate_tokens(agent.system_prompt + memory_prompt + skill_prompt + query)
    recent = history[-min_messages:]
    kept = list(recent)
    used = base_tokens + sum(estimate_tokens(m.content) for m in recent)
    dropped = len(history) - len(recent)
    for older in reversed(history[:-min_messages]):
        cost = estimate_tokens(older.content)
        if used + cost > budget:
            break
        kept.insert(0, older)
        used += cost
        dropped -= 1
    history_messages = [{"role": m.role, "content": m.content} for m in kept]

    return {
        "system": agent.system_prompt,
        "memory_prompt": memory_prompt,
        "skill_prompt": skill_prompt,
        "memories": memories,
        "skills": skills,
        "history_messages": history_messages,
        "context": {
            "historyMessages": len(history_messages),
            "droppedMessages": dropped,
            "estimatedTokens": used,
            "budgetTokens": budget,
            "memoriesRecalled": len(memories),
            "skillsLoaded": len(skills),
        },
    }


def _extract_memory(
    db: Session,
    conversation: Conversation,
    user_content: str,
    assistant_content: str,
) -> None:
    """从本轮对话中提取值得长期记住的事实，写入 Episodic 记忆。"""
    try:
        client = conversation_client_factory("deepseek-chat")
        system = (
            "你是对话记忆提取器。判断用户与智能体的这段对话中是否存在值得长期记住的信息："
            "项目事实、用户偏好、已确认的决策或约束。没有则返回空。只返回 JSON："
            '{"key": "简短英文标识", "content": "一句话中文记忆", "importance": 0.0-1.0}'
        )
        result = client.chat_json(system, f"用户：{user_content[:2000]}\n智能体：{assistant_content[:2000]}", temperature=0.1)
        data = result.data
        content = str(data.get("content") or "").strip()
        if len(content) < 4:
            return
        key = str(data.get("key") or f"conversation:{conversation.id[-8:]}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")[:160]
        importance = max(0.0, min(1.0, float(data.get("importance") or 0.6)))
        memory_service.create(db, conversation.project_id, MemoryCreate(
            agent_key=conversation.agent_key,
            scope="project",
            memory_type="episodic",
            key=key,
            content=content,
            importance=importance,
            tags=["conversation"],
            metadata={"conversationId": conversation.id},
        ))
        db.flush()
    except AppError:
        # 记忆提取失败不影响对话本身
        db.rollback()


TITLE_SYSTEM = "你是对话标题生成器。根据对话内容生成不超过 20 个字的简洁中文标题，只返回标题本身，不要引号、标点或任何解释。"


def _clean_title(value: str, fallback: str) -> str:
    title = str(value or "").strip().strip("「」\"'《》.。!！?？\n ")
    if not title:
        title = fallback.strip().replace("\n", " ")[:30]
    return title[:40]


def _generate_title(db: Session, conversation: Conversation, history: list[ConversationMessage], user_content: str, assistant_content: str) -> str:
    """用模型为对话生成标题；模型不可用时降级为首条消息截断。"""
    fallback = user_content.strip().replace("\n", " ")[:30]
    try:
        recent = [{"role": m.role, "content": m.content} for m in history[-6:]]
        recent += [
            {"role": "user", "content": user_content[:600]},
            {"role": "assistant", "content": assistant_content[:600]},
        ]
        client = conversation_client_factory("deepseek-chat")
        title = client.chat(TITLE_SYSTEM, recent, temperature=0.3)
        return _clean_title(title, fallback)
    except AppError:
        return fallback


def _to_camel(value: Any) -> Any:
    """SSE 事件不经 Pydantic 别名序列化，手动将键转为 camelCase。"""
    if isinstance(value, dict):
        return {to_camel(str(key)): _to_camel(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_camel(item) for item in value]
    return value


def sse_event(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(_to_camel(data), ensure_ascii=False, default=str)}\n\n"


class ConversationService:
    session_factory = SessionLocal

    def send_message(
        self,
        db: Session,
        conversation: Conversation,
        agent: AgentType,
        content: str,
        *,
        remember: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=content)
        db.add(user_message)
        db.flush()

        history = list(db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id, ConversationMessage.id != user_message.id)
            .order_by(ConversationMessage.created_at)
        ).all())
        context = build_chat_context(db, conversation, agent, history, content)

        messages = context["history_messages"] + [{"role": "user", "content": content}]
        # 系统上下文 = Agent 人设 + 长期记忆召回 + Skill 指令
        system_context = f"{agent.system_prompt}\n\n{context['memory_prompt']}\n\n{context['skill_prompt']}"
        client = conversation_client_factory(agent.model)
        reply = client.chat(system_context, messages, temperature=0.3)
        if not reply:
            raise AppError(502, "LLM_EMPTY_REPLY", "模型未返回有效回复")

        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
            metadata_json={
                "context": context["context"],
                "memoriesUsed": [m.id for m in context["memories"]],
                "model": agent.model,
            },
        )
        db.add(assistant_message)
        conversation.last_message_at = now
        conversation.updated_at = now
        if conversation.title == "新对话":
            conversation.title = _generate_title(db, conversation, history, content, reply)
        db.flush()

        if remember:
            _extract_memory(db, conversation, content, reply)

        db.commit()
        db.refresh(conversation)
        return {
            "conversation": conversation_response(db, conversation),
            "user_message": _message_dict(user_message),
            "assistant_message": _message_dict(assistant_message),
            "memories_used": [
                {
                    "id": m.id, "project_id": m.project_id, "agent_key": m.agent_key,
                    "scope": m.scope, "memory_type": m.memory_type, "key": m.key,
                    "content": m.content, "importance": m.importance, "tags": m.tags or [],
                    "metadata": m.metadata_json or {}, "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at, "expires_at": m.expires_at,
                    "created_at": m.created_at, "updated_at": m.updated_at,
                }
                for m in context["memories"]
            ],
            "context": context["context"],
        }

    def stream_message(
        self,
        project_id: str,
        conversation_id: str,
        agent: AgentType,
        content: str,
        *,
        remember: bool = True,
        user_id: str | None = None,
        client_ip: str = "",
    ) -> Iterator[str]:
        """SSE 流式对话：meta → delta* → (title) → done / error。

        使用可注入的会话工厂（测试时替换为测试库），保证流式响应期间请求级会话已回收也安全。
        """
        db = self.session_factory()
        try:
            conversation = db.scalar(
                select(Conversation).where(Conversation.id == conversation_id, Conversation.project_id == project_id)
            )
            if not conversation:
                yield sse_event({"type": "error", "code": "CONVERSATION_NOT_FOUND", "message": "对话不存在", "status": 404})
                return

            now = datetime.now(timezone.utc)
            user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=content)
            db.add(user_message)
            db.flush()

            history = list(db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id, ConversationMessage.id != user_message.id)
                .order_by(ConversationMessage.created_at)
            ).all())
            context = build_chat_context(db, conversation, agent, history, content)
            yield sse_event({"type": "meta", "context": context["context"]})

            system_context = f"{agent.system_prompt}\n\n{context['memory_prompt']}\n\n{context['skill_prompt']}"
            messages = context["history_messages"] + [{"role": "user", "content": content}]
            client = conversation_client_factory(agent.model)

            chunks: list[str] = []
            try:
                for chunk in client.chat_stream(system_context, messages, temperature=0.3):
                    chunks.append(chunk)
                    yield sse_event({"type": "delta", "content": chunk})
            except AppError as exc:
                db.rollback()
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                yield sse_event({
                    "type": "error",
                    "code": detail.get("code", "LLM_STREAM_FAILED"),
                    "message": detail.get("message", str(exc)),
                    "status": exc.status_code,
                })
                return

            reply = "".join(chunks).strip()
            if not reply:
                db.rollback()
                yield sse_event({"type": "error", "code": "LLM_EMPTY_REPLY", "message": "模型未返回有效回复", "status": 502})
                return

            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=reply,
                metadata_json={
                    "context": context["context"],
                    "memoriesUsed": [m.id for m in context["memories"]],
                    "model": agent.model,
                },
            )
            db.add(assistant_message)
            conversation.last_message_at = now
            conversation.updated_at = now
            new_title: str | None = None
            if conversation.title == "新对话":
                new_title = _generate_title(db, conversation, history, content, reply)
                conversation.title = new_title
                yield sse_event({"type": "title", "title": new_title})
            if remember:
                _extract_memory(db, conversation, content, reply)
            db.commit()
            db.refresh(conversation)
            yield sse_event({
                "type": "done",
                "conversation": conversation_response(db, conversation),
                "assistantMessage": _message_dict(assistant_message),
                "memoriesUsed": [
                    {
                        "id": m.id, "project_id": m.project_id, "agent_key": m.agent_key,
                        "scope": m.scope, "memory_type": m.memory_type, "key": m.key,
                        "content": m.content, "importance": m.importance, "tags": m.tags or [],
                        "metadata": m.metadata_json or {}, "access_count": m.access_count,
                        "last_accessed_at": m.last_accessed_at, "expires_at": m.expires_at,
                        "created_at": m.created_at, "updated_at": m.updated_at,
                    }
                    for m in context["memories"]
                ],
                "title": new_title,
                "userMessageId": user_message.id,
            })
        except Exception as exc:  # noqa: BLE001 —— SSE 边界：任何未预期错误都以事件形式返回
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            yield sse_event({"type": "error", "code": "STREAM_INTERNAL", "message": f"流式对话失败：{exc}", "status": 502})
        finally:
            db.close()

    def regenerate_title(self, db: Session, conversation: Conversation) -> str:
        """基于最近消息重新生成对话标题；无消息时抛出业务错误。"""
        from app.core.errors import AppError as _AppError

        messages = list(db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(8)
        ).all())
        if not messages:
            raise _AppError(409, "CONVERSATION_EMPTY", "对话暂无消息，无法生成标题")
        recent = [{"role": m.role, "content": m.content[:600]} for m in reversed(messages)]
        client = conversation_client_factory("deepseek-chat")
        title = client.chat(TITLE_SYSTEM, recent, temperature=0.3)
        return _clean_title(title, conversation.title)


conversation_service = ConversationService()
