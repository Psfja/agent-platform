from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import audit, get_current_user, require_platform_admin
from app.core.errors import AppError, conflict, not_found
from app.database import get_db
from app.models import AgentType, AgentTypeVersion, PipelineNode, PipelineTemplate, Task, User
from app.schemas import AgentTypeCreate, AgentTypeResponse, AgentTypeUpdate, AgentTypeUsage, PipelineNodeInput, PipelineTemplateCreate, PipelineTemplateResponse
from app.services.llm_client import ChatModel, OpenAICompatibleClient
from app.services.skill_loader import skill_registry

router = APIRouter(prefix="/admin", tags=["agent-and-pipeline-configuration"], dependencies=[Depends(require_platform_admin)])

pipeline_llm_client_factory: Callable[[str], ChatModel] = lambda model: OpenAICompatibleClient(model=model)


def agent_response(db: Session, item: AgentType) -> AgentTypeResponse:
    """附带引用统计（流程节点 / 模板名 / 进行中任务），供前端判断可删除性与展示。"""
    pipeline_nodes = db.scalar(select(func.count(PipelineNode.id)).where(PipelineNode.agent_type_id == item.id)) or 0
    template_names: list[str] = []
    if pipeline_nodes:
        rows = db.scalars(
            select(PipelineTemplate.display_name)
            .join(PipelineNode, PipelineNode.template_id == PipelineTemplate.id)
            .where(PipelineNode.agent_type_id == item.id)
            .distinct()
        ).all()
        template_names = list(rows)
    active_tasks = db.scalar(
        select(func.count(Task.id)).where(Task.agent_type.ilike(f"%{item.name}%"), Task.status.in_(["pending", "in_progress", "paused"]))
    ) or 0
    return AgentTypeResponse(
        id=item.id, name=item.name, display_name=item.display_name, description=item.description,
        system_prompt=item.system_prompt, model=item.model, temperature=getattr(item, "temperature", 0.2),
        tools=item.tools or [], skills=item.skills or [], sandbox_config=item.sandbox_config or {},
        version=item.version, is_template=item.is_template, is_active=item.is_active,
        usage=AgentTypeUsage(pipeline_nodes=pipeline_nodes, template_names=template_names, active_tasks=active_tasks),
        created_at=item.created_at, updated_at=item.updated_at,
    )


def template_response(db: Session, item: PipelineTemplate) -> PipelineTemplateResponse:
    nodes = db.scalars(select(PipelineNode).where(PipelineNode.template_id == item.id).order_by(PipelineNode.position)).all()
    return PipelineTemplateResponse(id=item.id, name=item.name, display_name=item.display_name, description=item.description, template_type=item.template_type, version=item.version, is_active=item.is_active, is_system=item.is_system, config=item.config or {}, nodes=[PipelineNodeInput(node_key=n.node_key, agent_type_id=n.agent_type_id, display_name=n.display_name, depends_on=n.depends_on or [], execution_mode=n.execution_mode, config=n.config or {}, position=n.position) for n in nodes], created_at=item.created_at, updated_at=item.updated_at)


def validate_skills(names: list[str]) -> None:
    loaded = {item.name for item in skill_registry.list()}
    missing = sorted(set(names) - loaded)
    if missing: raise conflict("SKILL_REFERENCE_INVALID", "AgentType 引用了未加载的 Skills", missing=missing)


@router.get("/agent-types", response_model=list[AgentTypeResponse])
def list_agent_types(db: Session = Depends(get_db)) -> list[AgentTypeResponse]:
    return [agent_response(db, item) for item in db.scalars(select(AgentType).order_by(AgentType.created_at)).all()]


@router.post("/agent-types", response_model=AgentTypeResponse, status_code=status.HTTP_201_CREATED)
def create_agent_type(payload: AgentTypeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AgentTypeResponse:
    if db.scalar(select(AgentType).where(AgentType.name == payload.name)): raise conflict("AGENT_TYPE_EXISTS", "智能体类型标识已存在")
    validate_skills(payload.skills)
    item = AgentType(**payload.model_dump(), version=1)
    db.add(item); db.flush(); db.add(AgentTypeVersion(agent_type_id=item.id, version=1, snapshot=payload.model_dump(), changed_by=user.id)); db.commit(); db.refresh(item)
    return agent_response(db, item)


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
    snapshot = agent_response(db, item).model_dump(mode="json")
    item.version += 1
    for key, value in changes.items(): setattr(item, key, value)
    db.add(AgentTypeVersion(agent_type_id=item.id, version=item.version, snapshot={**snapshot, **changes}, changed_by=user.id)); db.commit(); db.refresh(item)
    return agent_response(db, item)


@router.delete("/agent-types/{agent_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_type(agent_type_id: str, db: Session = Depends(get_db)):
    item = db.get(AgentType, agent_type_id)
    if not item: raise not_found("智能体类型", agent_type_id)
    references = db.scalar(select(func.count(PipelineNode.id)).where(PipelineNode.agent_type_id == item.id)) or 0
    template_names: list[str] = []
    if references:
        template_names = list(db.scalars(
            select(PipelineTemplate.display_name)
            .join(PipelineNode, PipelineNode.template_id == PipelineTemplate.id)
            .where(PipelineNode.agent_type_id == item.id)
            .distinct()
        ).all())
    active_tasks = db.scalar(select(func.count(Task.id)).where(Task.agent_type.ilike(f"%{item.name}%"), Task.status.in_(["pending", "in_progress", "paused"]))) or 0
    if references or active_tasks:
        raise conflict(
            "AGENT_TYPE_IN_USE",
            f"智能体类型正在被 {len(template_names)} 个流程模板和 {active_tasks} 个进行中任务使用，无法删除",
            pipelineNodes=references, templateNames=template_names, activeTasks=active_tasks,
        )
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


_NODE_KEY_RE = re.compile(r"[^a-z0-9-]+")
_ALLOWED_TEMPLATE_TYPES = {"fullstack", "api", "frontend", "custom"}


def _sanitize_key(value: Any, fallback: str) -> str:
    text = _NODE_KEY_RE.sub("-", str(value or "").strip().lower()).strip("-")
    if not text or not text[0].isalnum():
        text = f"{fallback}-{text}" if text else fallback
    return text[:79] or fallback


def _topo_sort_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按依赖关系做 Kahn 拓扑排序；依赖缺失或成环时保持稳定顺序。"""
    by_key = {n["nodeKey"]: n for n in nodes}
    remaining = {n["nodeKey"]: [d for d in n["dependsOn"] if d in by_key] for n in nodes}
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [key for key, deps in remaining.items() if not deps]
        if not ready:  # 成环：取第一个剩余节点打破环
            ready = [next(iter(remaining))]
        for key in sorted(ready, key=lambda k: next(i for i, n in enumerate(nodes) if n["nodeKey"] == k)):
            ordered.append(by_key[key])
            del remaining[key]
            for deps in remaining.values():
                if key in deps:
                    deps.remove(key)
    return ordered


@router.post("/pipeline-templates/generate")
def generate_pipeline(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """由自然语言需求描述生成流程编排草稿（真实调用模型网关，不做任何 Mock）。"""
    requirement = str(payload.get("requirement", "")).strip()
    if len(requirement) < 8:
        raise AppError(422, "PIPELINE_REQUIREMENT_TOO_SHORT", "请提供至少 8 个字符的流程需求描述")
    agents = db.scalars(select(AgentType).where(AgentType.is_active.is_(True)).order_by(AgentType.created_at)).all()
    if not agents:
        raise AppError(409, "AGENT_TYPE_UNAVAILABLE", "平台没有可用智能体类型，无法生成流程")
    catalog = [{"id": a.name, "name": a.display_name, "description": a.description} for a in agents]
    system = (
        "你是企业智能体平台中的「流程编排设计师」。根据用户对业务流程或软件需求的自然语言描述，"
        "输出一个多智能体协作流程的 JSON 对象。\n"
        "可选智能体类型（引用时必须使用其 id）：\n"
        f"{catalog}\n"
        "输出要求：\n"
        "1. 只返回一个 JSON 对象，不要使用 markdown 代码块或任何解释文字；\n"
        "2. 结构必须为：\n"
        '{"name": "小写英文标识", "displayName": "流程显示名称", "description": "流程说明", "templateType": "fullstack|api|frontend|custom", "nodes": [...]}\n'
        '3. nodes 中每个节点结构为 {"nodeKey": "简短英文标识", "agentTypeId": "必须来自上面的列表", "displayName": "节点职责名称", "dependsOn": ["依赖节点的 nodeKey"], "executionMode": "sequential|parallel"}；\n'
        "4. 没有依赖的节点 dependsOn 写 []；可并行的节点 executionMode 用 parallel 且共享相同依赖；\n"
        "5. 节点数量 3~10 个，必须覆盖用户描述的全部环节，并符合依赖顺序。"
    )
    user_prompt = f"请为以下需求设计多智能体协作流程：\n{requirement}"
    result = pipeline_llm_client_factory("deepseek-chat").chat_json(system, user_prompt, temperature=0.2)
    audit(db, user, "admin.pipeline.generate", resource_type="pipeline_template", metadata={"requirement": requirement[:500]}, request=request)

    data = result.data
    warnings: list[str] = []

    name = _sanitize_key(data.get("name"), "ai-flow")
    if db.scalar(select(PipelineTemplate).where(PipelineTemplate.name == name)):
        name = f"{name[:70]}-ai"
        warnings.append(f"流程标识已存在，已调整为 {name}")
    display_name = str(data.get("displayName") or "AI 生成流程").strip()[:120] or "AI 生成流程"
    description = str(data.get("description") or "").strip()[:5000] or "由 AI 根据需求自动生成的智能体协作流程。"
    template_type = str(data.get("templateType") or "custom").strip().lower()
    if template_type not in _ALLOWED_TEMPLATE_TYPES:
        template_type = "custom"

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise AppError(422, "PIPELINE_GENERATION_EMPTY", "模型未返回有效的流程节点", {"hint": "请调整需求描述后重试"})

    agent_map = {a.name: a for a in agents}
    nodes: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    for item in raw_nodes[:12]:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("agentTypeId") or "").strip()
        if agent_id not in agent_map:
            warnings.append(f"忽略了无效智能体引用：{agent_id or '(空)'}")
            continue
        base = _sanitize_key(item.get("nodeKey") or agent_id, "node")
        key, counter = base, 2
        while key in used_keys:
            key = f"{base}-{counter}"
            counter += 1
        used_keys.add(key)
        mode = str(item.get("executionMode") or "sequential").strip().lower()
        if mode not in {"sequential", "parallel"}:
            mode = "sequential"
        nodes.append({
            "nodeKey": key,
            "agentTypeId": agent_id,
            "displayName": str(item.get("displayName") or agent_map[agent_id].display_name).strip()[:80],
            "dependsOn": [],
            "executionMode": mode,
            "config": {},
            "position": len(nodes),
            "_raw_deps": [str(d).strip() for d in (item.get("dependsOn") or []) if isinstance(d, str) and str(d).strip()],
        })
    if not nodes:
        raise AppError(422, "PIPELINE_GENERATION_EMPTY", "模型返回的节点均无法引用平台智能体")

    for node in nodes:
        deps: list[str] = []
        for raw in node.pop("_raw_deps"):
            if raw == node["nodeKey"]:
                warnings.append(f"节点 {node['nodeKey']} 不能依赖自身，已忽略")
                continue
            if any(n["nodeKey"] == raw for n in nodes):
                deps.append(raw)
            else:
                warnings.append(f"节点 {node['nodeKey']} 的依赖 {raw} 不存在，已忽略")
        node["dependsOn"] = deps

    ordered = _topo_sort_nodes(nodes)
    for index, node in enumerate(ordered):
        node["position"] = index

    return {
        "draft": {"name": name, "displayName": display_name, "description": description, "templateType": template_type, "nodes": ordered},
        "warnings": warnings[:10],
    }
