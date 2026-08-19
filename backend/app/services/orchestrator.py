from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Iteration, Project, Task, TaskLog, uuid_str
from app.services.memory import memory_service
from app.services.skill_loader import skill_registry

AGENT_KEY_MAP = {
    "架构设计": "architect",
    "后端开发": "backend-developer",
    "前端开发": "frontend-developer",
    "数据库设计": "database-engineer",
    "代码审查": "code-reviewer",
    "测试工程师": "test-engineer",
}

AGENT_TASKS = {
    "架构设计": ("AR", "增量技术方案设计", "读取现有代码和架构文档，形成最小化变更方案。"),
    "后端开发": ("BE", "后端增量开发", "只修改受影响的服务、接口与测试代码。"),
    "前端开发": ("FE", "前端增量开发", "实现受影响页面的新增交互并保持现有体验。"),
    "数据库设计": ("DB", "向前兼容数据库迁移", "通过新增字段或表完成兼容性迁移。"),
    "代码审查": ("CR", "增量代码审查", "检查兼容性、安全性和重复实现。"),
    "测试工程师": ("QA", "回归测试与质量验证", "运行已有测试并生成针对本次变更的新增用例。"),
}


def create_initial_project_task(db: Session, project: Project) -> Task:
    loaded_skills = [skill.name for skill in skill_registry.list("project-manager")]
    task = Task(
        id=f"task-{uuid_str()}",
        project_id=project.id,
        name="需求理解与项目规划",
        agent_type="项目经理智能体",
        agent_short="PM",
        description="分析初始需求并生成结构化需求说明书。",
        status="in_progress",
        progress=8,
        task_type="initial",
        current_action="正在识别业务场景、用户角色与核心流程",
        execution_metadata={"agentKey": "project-manager", "loadedSkills": loaded_skills, "memoryIds": []},
        started_at=datetime.now(timezone.utc),
        thread_id=f"thread-{uuid_str()}",
    )
    db.add(task)
    project.tasks_total = 1
    project.tasks_done = 0
    project.progress = 8
    project.status = "planning"
    db.flush()
    db.add(TaskLog(task_id=task.id, level="system", event_type="lifecycle", message="项目经理智能体已启动。"))
    db.add(TaskLog(task_id=task.id, level="info", event_type="skill_loaded", message=f"已加载 {len(loaded_skills)} 个 Skills：{', '.join(loaded_skills) or '无'}。"))
    db.add(TaskLog(task_id=task.id, level="info", event_type="message", message="正在分析初始需求的完整性。"))
    return task


def create_iteration_tasks(db: Session, project: Project, iteration: Iteration, agents: Iterable[str]) -> list[Task]:
    now = datetime.now(timezone.utc)
    root_memories = memory_service.retrieve(db, project.id, "project-manager", iteration.change_request, limit=5, touch=True)
    root_skills = skill_registry.list("project-manager")
    root = Task(
        id=f"task-{uuid_str()}", project_id=project.id, iteration_id=iteration.id,
        name=f"{iteration.version} 增量迭代协调", agent_type="项目经理智能体", agent_short="PM",
        description="协调增量任务依赖、风险和交付状态。", status="in_progress", progress=5,
        task_type="incremental", current_action="正在下发增量任务", started_at=now,
        execution_metadata={"agentKey": "project-manager", "loadedSkills": [s.name for s in root_skills], "memoryIds": [m.id for m in root_memories]},
        thread_id=f"thread-{uuid_str()}",
    )
    db.add(root)
    db.flush()
    db.add(TaskLog(task_id=root.id, level="info", event_type="runtime_context", message=f"运行时上下文已加载：{len(root_memories)} 条记忆，{len(root_skills)} 个 Skills。", metadata_json={"memoryIds": [m.id for m in root_memories], "skills": [s.name for s in root_skills]}))
    tasks = [root]
    previous_id: str | None = root.id
    for index, agent in enumerate(agents):
        short, name, description = AGENT_TASKS.get(agent, ("AI", f"{agent}任务", "执行增量变更任务。"))
        agent_key = AGENT_KEY_MAP.get(agent, "general-purpose")
        loaded_skills = skill_registry.list(agent_key)
        recalled_memories = memory_service.retrieve(db, project.id, agent_key, iteration.change_request, limit=5, touch=True)
        is_first = index == 0
        task = Task(
            id=f"task-{uuid_str()}", project_id=project.id, iteration_id=iteration.id,
            parent_task_id=root.id if agent not in {"代码审查", "测试工程师"} else previous_id,
            name=name, agent_type=f"{agent}智能体", agent_short=short, description=description,
            status="in_progress" if is_first else "pending", progress=3 if is_first else 0,
            task_type="incremental", current_action="正在加载项目上下文" if is_first else "",
            execution_metadata={"agentKey": agent_key, "loadedSkills": [s.name for s in loaded_skills], "memoryIds": [m.id for m in recalled_memories], "sandboxBackend": "configured"},
            started_at=now if is_first else None, thread_id=f"thread-{uuid_str()}",
        )
        db.add(task)
        db.flush()
        tasks.append(task)
        previous_id = task.id
        db.add(TaskLog(task_id=task.id, level="info", event_type="runtime_context", message=f"已绑定 {len(loaded_skills)} 个 Skills，并召回 {len(recalled_memories)} 条持久记忆。", metadata_json={"skills": [s.name for s in loaded_skills], "memoryIds": [m.id for m in recalled_memories]}))
        if is_first:
            db.add(TaskLog(task_id=task.id, level="system", event_type="lifecycle", message=f"{agent}智能体已启动。"))
            db.add(TaskLog(task_id=task.id, level="info", event_type="message", message="已加载代码结构、API 清单和历史需求。"))
    project.status = "executing"
    project.version = iteration.version
    project.tasks_total += len(tasks)
    project.updated_at = now
    iteration.status = "executing"
    return tasks


def recalculate_project(db: Session, project: Project) -> None:
    rows = db.execute(
        select(Task.status, func.count(Task.id)).where(Task.project_id == project.id).group_by(Task.status)
    ).all()
    counts = dict(rows)
    total = sum(counts.values())
    completed = counts.get("completed", 0)
    project.tasks_total = total
    project.tasks_done = completed
    if total:
        task_progress = db.scalar(select(func.avg(Task.progress)).where(Task.project_id == project.id)) or 0
        project.progress = max(0, min(100, round(float(task_progress))))
