from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import audit, get_current_user
from app.core.errors import conflict, not_found
from app.database import get_db
from app.models import AgentType, Conversation, ConversationInterrupt, ConversationMessage, User
from app.schemas import (
    AgentDecisionResponse,
    ChatTurnResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationUpdate,
    InterruptDecideRequest,
    InterruptResponse,
)
from app.services.conversation import conversation_response as build_conversation_response, conversation_service
from app.services.conversation_agent import conversation_agent_runtime

router = APIRouter(tags=["conversations"])


def _get_conversation_or_404(db: Session, project_id: str, conversation_id: str) -> Conversation:
    item = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.project_id == project_id)
    )
    if not item:
        raise not_found("对话", conversation_id)
    return item


def _get_agent_or_404(db: Session, agent_key: str) -> AgentType:
    agent = db.scalar(select(AgentType).where(AgentType.name == agent_key))
    if not agent:
        raise not_found("智能体类型", agent_key)
    if not agent.is_active:
        raise conflict("AGENT_TYPE_INACTIVE", "该智能体类型已停用，无法发起对话")
    return agent


def _message_response(item: ConversationMessage) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=item.id, role=item.role, content=item.content,
        metadata=item.metadata_json or {}, created_at=item.created_at,
    )


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationResponse])
def list_conversations(project_id: str, agent_key: str | None = None, db: Session = Depends(get_db)) -> list[ConversationResponse]:
    statement = select(Conversation).where(Conversation.project_id == project_id)
    if agent_key:
        statement = statement.where(Conversation.agent_key == agent_key)
    items = db.scalars(statement.order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [ConversationResponse(**build_conversation_response(db, item)) for item in items]


@router.post("/projects/{project_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(project_id: str, payload: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConversationResponse:
    _get_agent_or_404(db, payload.agent_key)
    item = Conversation(
        project_id=project_id,
        agent_key=payload.agent_key,
        title=payload.title.strip()[:200] or "新对话",
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    audit(db, user, "conversation.create", project_id=project_id, resource_type="conversation", resource_id=item.id, metadata={"agentKey": payload.agent_key})
    db.commit()
    db.refresh(item)
    return ConversationResponse(**build_conversation_response(db, item))


@router.get("/projects/{project_id}/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(project_id: str, conversation_id: str, db: Session = Depends(get_db)) -> ConversationDetailResponse:
    item = _get_conversation_or_404(db, project_id, conversation_id)
    messages = list(db.scalars(
        select(ConversationMessage).where(ConversationMessage.conversation_id == item.id).order_by(ConversationMessage.created_at)
    ).all())
    return ConversationDetailResponse(
        **build_conversation_response(db, item),
        messages=[_message_response(m) for m in messages],
    )


@router.patch("/projects/{project_id}/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(project_id: str, conversation_id: str, payload: ConversationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConversationResponse:
    item = _get_conversation_or_404(db, project_id, conversation_id)
    if payload.title is not None:
        item.title = payload.title.strip()[:200]
    if payload.mode is not None:
        item.mode = payload.mode
    audit(db, user, "conversation.update", project_id=project_id, resource_type="conversation", resource_id=item.id, metadata={"mode": item.mode})
    db.commit()
    db.refresh(item)
    return ConversationResponse(**build_conversation_response(db, item))


@router.delete("/projects/{project_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(project_id: str, conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_conversation_or_404(db, project_id, conversation_id)
    audit(db, user, "conversation.delete", project_id=project_id, resource_type="conversation", resource_id=item.id)
    db.delete(item)
    db.commit()
    return None


@router.post("/projects/{project_id}/conversations/{conversation_id}/messages", response_model=ChatTurnResponse)
def send_message(project_id: str, conversation_id: str, payload: ConversationMessageCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatTurnResponse:
    """发送消息：召回长期记忆 → 组装上下文（含 Token 预算裁剪）→ 模型回复 → 提取记忆。"""
    item = _get_conversation_or_404(db, project_id, conversation_id)
    agent = _get_agent_or_404(db, item.agent_key)
    result = conversation_service.send_message(db, item, agent, payload.content, remember=payload.remember)
    audit(db, user, "conversation.message", project_id=project_id, resource_type="conversation", resource_id=item.id, metadata={"role": "user"}, request=request)
    return ChatTurnResponse(**result)


@router.post("/projects/{project_id}/conversations/{conversation_id}/messages/stream")
def stream_message(project_id: str, conversation_id: str, payload: ConversationMessageCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    """SSE 流式对话：事件序列 meta → delta* → (title) → done，异常时输出 error 事件。

    前端使用 fetch + ReadableStream 解析（POST 无法使用 EventSource）。
    """
    item = _get_conversation_or_404(db, project_id, conversation_id)
    agent = _get_agent_or_404(db, item.agent_key)
    client_ip = request.client.host if request.client else ""
    if item.mode == "agent":
        # DeepAgents 工具模式：带 FilesystemBackend + 沙箱 + 子智能体委派 + HITL
        stream = conversation_agent_runtime.stream(db, project_id, item, agent, payload.content)
    else:
        stream = conversation_service.stream_message(
            project_id, conversation_id, agent, payload.content,
            remember=payload.remember, user_id=user.id, client_ip=client_ip,
        )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/projects/{project_id}/conversations/{conversation_id}/title", response_model=ConversationResponse)
def regenerate_title(project_id: str, conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConversationResponse:
    """基于最近消息用模型重新生成对话标题；未配置模型网关时返回 503。"""
    item = _get_conversation_or_404(db, project_id, conversation_id)
    item.title = conversation_service.regenerate_title(db, item)
    audit(db, user, "conversation.title", project_id=project_id, resource_type="conversation", resource_id=item.id)
    db.commit()
    db.refresh(item)
    return ConversationResponse(**build_conversation_response(db, item))


@router.get("/projects/{project_id}/conversations/{conversation_id}/interrupts", response_model=list[InterruptResponse])
def list_interrupts(project_id: str, conversation_id: str, db: Session = Depends(get_db)) -> list[InterruptResponse]:
    item = _get_conversation_or_404(db, project_id, conversation_id)
    rows = db.scalars(
        select(ConversationInterrupt)
        .where(ConversationInterrupt.conversation_id == item.id, ConversationInterrupt.status == "pending")
        .order_by(ConversationInterrupt.created_at)
    ).all()
    return [
        InterruptResponse(id=row.id, conversation_id=row.conversation_id, tool_name=row.tool_name, payload=row.payload_json or {}, status=row.status, created_at=row.created_at)
        for row in rows
    ]


@router.post("/projects/{project_id}/conversations/{conversation_id}/interrupts/{interrupt_id}/decide", response_model=AgentDecisionResponse)
def decide_interrupt(project_id: str, conversation_id: str, interrupt_id: str, payload: InterruptDecideRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AgentDecisionResponse:
    """人工审批 DeepAgents 中断：approve / edit / reject，随后 Agent 从检查点恢复继续执行。"""
    item = _get_conversation_or_404(db, project_id, conversation_id)
    interrupt = db.scalar(
        select(ConversationInterrupt).where(
            ConversationInterrupt.id == interrupt_id,
            ConversationInterrupt.conversation_id == item.id,
            ConversationInterrupt.status == "pending",
        )
    )
    if not interrupt:
        raise not_found("待审批请求", interrupt_id)
    agent = _get_agent_or_404(db, item.agent_key)
    result = conversation_agent_runtime.decide(
        db, item, agent, interrupt, payload.decision, payload.reason, payload.edited_action,
    )
    from app.core.auth import audit
    audit(db, user, "conversation.approval", project_id=project_id, resource_type="conversation", resource_id=item.id, metadata={"decision": payload.decision, "tool": interrupt.tool_name})
    db.commit()
    return AgentDecisionResponse(**result)


@router.get("/projects/{project_id}/conversations/{conversation_id}/workspace")
def conversation_workspace(project_id: str, conversation_id: str, db: Session = Depends(get_db)) -> dict:
    _get_conversation_or_404(db, project_id, conversation_id)
    return {"files": conversation_agent_runtime.workspace_files(project_id)}
