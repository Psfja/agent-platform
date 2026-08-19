from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_platform_admin
from app.core.errors import conflict, not_found
from app.database import get_db
from app.models import AgentType, AgentTypeVersion, PipelineNode, PipelineTemplate, Task, User
from app.schemas import AgentTypeCreate, AgentTypeResponse, AgentTypeUpdate, PipelineNodeInput, PipelineTemplateCreate, PipelineTemplateResponse
from app.services.skill_loader import skill_registry

router = APIRouter(prefix="/admin", tags=["agent-and-pipeline-configuration"], dependencies=[Depends(require_platform_admin)])


def agent_response(item: AgentType) -> AgentTypeResponse:
    return AgentTypeResponse(id=item.id, name=item.name, display_name=item.display_name, description=item.description, system_prompt=item.system_prompt, model=item.model, tools=item.tools or [], skills=item.skills or [], sandbox_config=item.sandbox_config or {}, version=item.version, is_template=item.is_template, is_active=item.is_active, created_at=item.created_at, updated_at=item.updated_at)


def template_response(db: Session, item: PipelineTemplate) -> PipelineTemplateResponse:
    nodes = db.scalars(select(PipelineNode).where(PipelineNode.template_id == item.id).order_by(PipelineNode.position)).all()
    return PipelineTemplateResponse(id=item.id, name=item.name, display_name=item.display_name, description=item.description, template_type=item.template_type, version=item.version, is_active=item.is_active, is_system=item.is_system, config=item.config or {}, nodes=[PipelineNodeInput(node_key=n.node_key, agent_type_id=n.agent_type_id, display_name=n.display_name, depends_on=n.depends_on or [], execution_mode=n.execution_mode, config=n.config or {}, position=n.position) for n in nodes], created_at=item.created_at, updated_at=item.updated_at)


def validate_skills(names: list[str]) -> None:
    loaded = {item.name for item in skill_registry.list()}
    missing = sorted(set(names) - loaded)
    if missing: raise conflict("SKILL_REFERENCE_INVALID", "AgentType 引用了未加载的 Skills", missing=missing)


@router.get("/agent-types", response_model=list[AgentTypeResponse])
def list_agent_types(db: Session = Depends(get_db)) -> list[AgentTypeResponse]:
    return [agent_response(item) for item in db.scalars(select(AgentType).order_by(AgentType.created_at)).all()]


@router.post("/agent-types", response_model=AgentTypeResponse, status_code=status.HTTP_201_CREATED)
def create_agent_type(payload: AgentTypeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AgentTypeResponse:
    if db.scalar(select(AgentType).where(AgentType.name == payload.name)): raise conflict("AGENT_TYPE_EXISTS", "智能体类型标识已存在")
    validate_skills(payload.skills)
    item = AgentType(**payload.model_dump(), version=1)
    db.add(item); db.flush(); db.add(AgentTypeVersion(agent_type_id=item.id, version=1, snapshot=payload.model_dump(), changed_by=user.id)); db.commit(); db.refresh(item)
    return agent_response(item)


@router.get("/agent-types/{agent_type_id}", response_model=AgentTypeResponse)
def get_agent_type(agent_type_id: str, db: Session = Depends(get_db)) -> AgentTypeResponse:
    item = db.get(AgentType, agent_type_id)
    if not item: raise not_found("智能体类型", agent_type_id)
    return agent_response(item)


@router.patch("/agent-types/{agent_type_id}", response_model=AgentTypeResponse)
def update_agent_type(agent_type_id: str, payload: AgentTypeUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AgentTypeResponse:
    item = db.get(AgentType, agent_type_id)
    if not item: raise not_found("智能体类型", agent_type_id)
    changes = payload.model_dump(exclude_unset=True)
    if "skills" in changes: validate_skills(changes["skills"] or [])
    snapshot = agent_response(item).model_dump(mode="json")
    item.version += 1
    for key, value in changes.items(): setattr(item, key, value)
    db.add(AgentTypeVersion(agent_type_id=item.id, version=item.version, snapshot={**snapshot, **changes}, changed_by=user.id)); db.commit(); db.refresh(item)
    return agent_response(item)


@router.delete("/agent-types/{agent_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_type(agent_type_id: str, db: Session = Depends(get_db)):
    item = db.get(AgentType, agent_type_id)
    if not item: raise not_found("智能体类型", agent_type_id)
    references = db.scalar(select(func.count(PipelineNode.id)).where(PipelineNode.agent_type_id == item.id)) or 0
    active_tasks = db.scalar(select(func.count(Task.id)).where(Task.agent_type.ilike(f"%{item.display_name}%"), Task.status.in_(["pending", "in_progress", "paused"]))) or 0
    if references or active_tasks: raise conflict("AGENT_TYPE_IN_USE", "智能体类型正在被流程或任务使用", pipelineNodes=references, activeTasks=active_tasks)
    db.delete(item); db.commit(); return None


def validate_nodes(db: Session, nodes: list[PipelineNodeInput]) -> None:
    keys = {node.node_key for node in nodes}
    if len(keys) != len(nodes): raise conflict("PIPELINE_NODE_DUPLICATE", "流程节点标识重复")
    for node in nodes:
        agent = db.get(AgentType, node.agent_type_id)
        if not agent or not agent.is_active: raise conflict("AGENT_TYPE_UNAVAILABLE", "流程引用的智能体不存在或已停用", agentTypeId=node.agent_type_id)
        missing = set(node.depends_on) - keys
        if missing: raise conflict("PIPELINE_DEPENDENCY_INVALID", "流程节点依赖不存在", node=node.node_key, missing=sorted(missing))
        if node.node_key in node.depends_on: raise conflict("PIPELINE_CYCLE_INVALID", "节点不能依赖自身", node=node.node_key)


@router.get("/pipeline-templates", response_model=list[PipelineTemplateResponse])
def list_pipeline_templates(db: Session = Depends(get_db)) -> list[PipelineTemplateResponse]:
    return [template_response(db, item) for item in db.scalars(select(PipelineTemplate).order_by(PipelineTemplate.created_at)).all()]


@router.post("/pipeline-templates", response_model=PipelineTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline_template(payload: PipelineTemplateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PipelineTemplateResponse:
    if db.scalar(select(PipelineTemplate).where(PipelineTemplate.name == payload.name)): raise conflict("PIPELINE_TEMPLATE_EXISTS", "流程模板标识已存在")
    validate_nodes(db, payload.nodes)
    item = PipelineTemplate(name=payload.name, display_name=payload.display_name, description=payload.description, template_type=payload.template_type, is_active=payload.is_active, config=payload.config, created_by=user.id)
    db.add(item); db.flush()
    for node in payload.nodes: db.add(PipelineNode(template_id=item.id, **node.model_dump()))
    db.commit(); db.refresh(item); return template_response(db, item)


@router.get("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
def get_pipeline_template(template_id: str, db: Session = Depends(get_db)) -> PipelineTemplateResponse:
    item = db.get(PipelineTemplate, template_id)
    if not item: raise not_found("流程模板", template_id)
    return template_response(db, item)


@router.put("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
def update_pipeline_template(template_id: str, payload: PipelineTemplateCreate, db: Session = Depends(get_db)) -> PipelineTemplateResponse:
    item = db.get(PipelineTemplate, template_id)
    if not item: raise not_found("流程模板", template_id)
    validate_nodes(db, payload.nodes)
    item.display_name=payload.display_name; item.description=payload.description; item.template_type=payload.template_type; item.is_active=payload.is_active; item.config=payload.config; item.version += 1
    for node in db.scalars(select(PipelineNode).where(PipelineNode.template_id == item.id)).all(): db.delete(node)
    db.flush()
    for node in payload.nodes: db.add(PipelineNode(template_id=item.id, **node.model_dump()))
    db.commit(); db.refresh(item); return template_response(db, item)


@router.post("/pipeline-templates/recommend")
def recommend_pipeline(payload: dict, db: Session = Depends(get_db)) -> dict:
    requirement = str(payload.get("requirement", "")).lower()
    kind = "frontend" if any(word in requirement for word in ["前端", "页面", "看板"]) and not any(word in requirement for word in ["后端", "api", "数据库"]) else "api" if any(word in requirement for word in ["api", "接口", "微服务"]) and not any(word in requirement for word in ["页面", "前端"]) else "fullstack"
    item = db.scalar(select(PipelineTemplate).where(PipelineTemplate.template_type == kind, PipelineTemplate.is_active.is_(True)).order_by(PipelineTemplate.is_system.desc()))
    return {"template": template_response(db, item).model_dump(by_alias=True) if item else None, "reason": f"根据需求关键词推荐 {kind} 流程"}
