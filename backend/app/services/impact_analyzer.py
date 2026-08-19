from __future__ import annotations

import re
from typing import Any


def next_minor_version(current: str) -> str:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", current or "")
    if not match:
        return "v1.0.0"
    major, minor, _patch = (int(part) for part in match.groups())
    return f"v{major}.{minor + 1}.0"


def title_from_request(change_request: str) -> str:
    cleaned = re.sub(r"[。！!？?].*$", "", change_request.strip())
    cleaned = re.sub(r"^(请|希望|需要|我想要|新增|增加)", "", cleaned).strip()
    return (cleaned[:28] or "增量需求变更") + ("…" if len(cleaned) > 28 else "")


def analyze_change(change_request: str, current_version: str) -> dict[str, Any]:
    """可重复、无外部依赖的规则分析器，用于本地演示与接口联调。"""
    text = change_request.lower()
    destructive_words = ("删除", "移除", "重命名", "替换核心", "清空", "废弃接口")
    architecture_words = ("重构", "微服务", "架构", "拆分服务", "更换数据库")
    database_words = ("数据库", "字段", "表结构", "schema", "索引", "数据迁移")
    frontend_words = ("页面", "按钮", "交互", "看板", "前端", "界面", "导出")
    backend_words = ("接口", "api", "服务", "审批", "导出", "计算", "权限")
    auth_words = ("权限", "角色", "管理员", "审计")

    breaking = [word for word in destructive_words if word in text]
    architecture = any(word in text for word in architecture_words)
    database_change = any(word in text for word in database_words)
    existing_api_impact = any(word in text for word in ("修改接口", "接口签名", "废弃接口"))

    modules: list[dict[str, str]] = []
    agents: list[str] = []
    estimated_min = 2
    estimated_max = 4

    if any(word in text for word in backend_words) or not any(word in text for word in frontend_words):
        modules.append({"name": "后端 · 业务服务", "change": "新增或扩展服务能力", "risk": "low"})
        agents.append("后端开发")
        estimated_min += 3
        estimated_max += 5
    if any(word in text for word in frontend_words):
        modules.append({"name": "前端 · 业务页面", "change": "新增交互与状态反馈", "risk": "low"})
        agents.append("前端开发")
        estimated_min += 2
        estimated_max += 3
    if any(word in text for word in auth_words):
        modules.append({"name": "权限 · 访问控制", "change": "复用并扩展现有权限规则", "risk": "medium"})
        estimated_min += 1
        estimated_max += 2
    if database_change:
        modules.append({"name": "数据库 · Schema", "change": "向前兼容迁移", "risk": "medium"})
        agents.append("数据库设计")
        estimated_min += 1
        estimated_max += 3
    if architecture:
        modules.append({"name": "架构 · 核心设计", "change": "更新增量架构方案", "risk": "high"})
        agents.insert(0, "架构设计")

    agents.extend(["代码审查", "测试工程师"])
    agents = list(dict.fromkeys(agents))
    risk_level = "high" if breaking or architecture else "medium" if database_change or auth_words[0] in text else "low"
    change_type = "architecture" if architecture else "fix" if any(word in text for word in ("修复", "bug", "问题")) else "feature"

    recommendations = ["只修改受影响代码段，保留已有接口签名", "将新增用例并执行完整回归测试"]
    if "导出" in text:
        recommendations.insert(0, "大数据量导出建议采用异步任务，并设置单次数据上限")
    if database_change:
        recommendations.append("使用新增字段/表的向前兼容迁移，不删除现有结构")
    if breaking:
        recommendations.append("检测到潜在破坏性操作，执行前必须再次人工确认")

    return {
        "proposed_version": next_minor_version(current_version),
        "risk_level": risk_level,
        "change_type": change_type,
        "summary": f"识别到 {len(modules)} 个受影响模块；将采用最小化改动策略。",
        "modules": modules,
        "estimated_files": {"min": estimated_min, "max": estimated_max},
        "database_change": database_change,
        "database_strategy": "新增字段/表并提供可回滚迁移" if database_change else "无 Schema 变更",
        "existing_api_impact": existing_api_impact,
        "breaking_changes": [f"需求包含潜在破坏性操作：{word}" for word in breaking],
        "suggested_agents": agents,
        "estimated_tasks": len(agents) + (1 if architecture else 0),
        "recommendations": recommendations,
    }
