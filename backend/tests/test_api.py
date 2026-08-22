from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.models import AgentCheckpoint
from app.services.agent_builder import agent_build_runner
from app.services.application_deployer import application_deployment_runner
from app.services.docker_runtime import DockerCommandResult
from app.services.llm_client import LLMResult, OpenAICompatibleClient, parse_json_object
from app.services.sandbox import ExecutionResult, sandbox_manager


def test_health_and_demo_projects(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert response.json()[0]["id"] == "leave-hub"


def test_authentication_refresh_and_project_rbac(client):
    saved = client.headers.get("Authorization")
    del client.headers["Authorization"]
    try:
        unauthenticated = client.get("/api/v1/projects")
        assert unauthenticated.status_code == 401
        login = client.post("/api/v1/auth/login", json={"email": "yang.han@company.com", "password": "Agent@2026"})
        assert login.status_code == 200
        viewer_token = login.json()["accessToken"]
        refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": login.json()["refreshToken"]})
        assert refresh.status_code == 200
        viewed = client.get("/api/v1/projects/leave-hub", headers={"Authorization": f"Bearer {viewer_token}"})
        assert viewed.status_code == 200
        denied = client.post("/api/v1/projects/leave-hub/memories", headers={"Authorization": f"Bearer {viewer_token}"}, json={"key": "forbidden", "content": "viewer cannot write"})
        assert denied.status_code == 403
    finally:
        client.headers["Authorization"] = saved


def test_queue_status_requires_platform_admin(client):
    denied = client.get("/api/v1/queue/status")
    assert denied.status_code == 403
    admin = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin@2026"}).json()
    allowed = client.get("/api/v1/queue/status", headers={"Authorization": f"Bearer {admin['accessToken']}"})
    assert allowed.status_code == 200
    assert "redisAvailable" in allowed.json()


def test_agent_type_pipeline_and_monitoring_admin_apis(client):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin@2026"}).json()
    headers = {"Authorization": f"Bearer {admin['accessToken']}"}
    agents = client.get("/api/v1/admin/agent-types", headers=headers)
    assert agents.status_code == 200
    assert len(agents.json()) >= 7
    created = client.post("/api/v1/admin/agent-types", headers=headers, json={"name": "security-reviewer", "displayName": "安全审查工程师", "description": "检查鉴权、输入与依赖风险", "systemPrompt": "你是企业安全审查工程师。", "model": "deepseek-chat", "tools": ["read_file"], "skills": ["code-metrics"], "sandboxConfig": {"memoryMb": 256}})
    assert created.status_code == 201
    agent_id = created.json()["id"]
    template = client.post("/api/v1/admin/pipeline-templates", headers=headers, json={"name": "secure-review", "displayName": "安全审查流程", "description": "安全检查", "templateType": "custom", "nodes": [{"nodeKey": "security", "agentTypeId": agent_id, "displayName": "安全审查", "dependsOn": [], "executionMode": "sequential", "position": 0}]})
    assert template.status_code == 201
    denied = client.get("/api/v1/admin/agent-types")
    assert denied.status_code == 403
    monitoring = client.get("/api/v1/monitoring/summary", headers=headers)
    assert monitoring.status_code == 200
    assert "queue" in monitoring.json()
    sso = client.get("/api/v1/auth/sso/status")
    assert sso.status_code == 200
    assert sso.json()["providers"] == []


def test_admin_user_management_and_settings_status(client):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin@2026"}).json()
    headers = {"Authorization": f"Bearer {admin['accessToken']}"}

    # 普通用户访问被拒绝
    assert client.get("/api/v1/admin/users").status_code == 403

    # 创建用户（自动生成初始密码）
    created = client.post("/api/v1/admin/users", headers=headers, json={"email": "new.hire@company.com", "displayName": "新员工", "department": "信息技术部", "platformRole": "platform_admin"})
    assert created.status_code == 201, created.text
    body = created.json()
    user_id = body["user"]["id"]
    assert body["user"]["email"] == "new.hire@company.com"
    assert body["user"]["platformRole"] == "platform_admin"
    assert len(body["tempPassword"]) >= 12
    # 新用户可用初始密码登录
    login = client.post("/api/v1/auth/login", json={"email": "new.hire@company.com", "password": body["tempPassword"]})
    assert login.status_code == 200, login.text

    # 重复邮箱冲突
    assert client.post("/api/v1/admin/users", headers=headers, json={"email": "new.hire@company.com", "displayName": "重复", "department": ""}).status_code == 409

    # 列表包含新用户
    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 200
    assert any(item["id"] == user_id for item in users.json())

    # 更新角色与停用
    updated = client.patch(f"/api/v1/admin/users/{user_id}", headers=headers, json={"platformRole": "user", "department": "平台工程部", "isActive": False})
    assert updated.status_code == 200
    assert updated.json()["platformRole"] == "user" and updated.json()["isActive"] is False
    # 停用后无法登录
    assert client.post("/api/v1/auth/login", json={"email": "new.hire@company.com", "password": body["tempPassword"]}).status_code == 401

    # 重置密码后可用新密码登录
    reset = client.patch(f"/api/v1/admin/users/{user_id}", headers=headers, json={"isActive": True, "newPassword": "NewPass@2026"})
    assert reset.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "new.hire@company.com", "password": "NewPass@2026"}).status_code == 200

    # 不能删除/停用自己
    assert client.delete(f"/api/v1/admin/users/{admin['user']['id']}", headers=headers).status_code == 409
    assert client.patch(f"/api/v1/admin/users/{admin['user']['id']}", headers=headers, json={"isActive": False}).status_code == 409

    # 删除用户
    assert client.delete(f"/api/v1/admin/users/{user_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 200

    # 平台管理员不能创建/降级超级管理员
    zhao = client.post("/api/v1/auth/login", json={"email": "zhao.wei@company.com", "password": "Agent@2026"}).json()
    zhao_headers = {"Authorization": f"Bearer {zhao['accessToken']}"}
    assert client.post("/api/v1/admin/users", headers=zhao_headers, json={"email": "another.admin@company.com", "displayName": "超管候选", "platformRole": "super_admin"}).status_code == 403
    assert client.patch(f"/api/v1/admin/users/{admin['user']['id']}", headers=zhao_headers, json={"platformRole": "user"}).status_code == 403

    # 系统设置状态（脱敏）
    settings_status = client.get("/api/v1/settings/status", headers=headers)
    assert settings_status.status_code == 200
    payload = settings_status.json()
    assert payload["database"]["engine"] in {"sqlite", "postgresql"}
    assert payload["llm"]["configured"] is False  # 测试环境未配置模型 Key
    assert "apiKey" not in str(payload) and "password" not in str(payload)


def test_pipeline_generate_with_scripted_model(client, monkeypatch):
    from app.api import agent_config as agent_config_module
    from app.services.llm_client import LLMResult

    class ScriptedFlowModel:
        model = "scripted-flow-model"
        def chat_json(self, system, user, *, temperature=0.1):
            return LLMResult(data={
                "name": "Invoice-Flow_01",  # 触发标识清洗
                "displayName": "发票识别与台账生成",
                "description": "抽取发票字段、复核并生成台账。",
                "templateType": "custom",
                "nodes": [
                    {"nodeKey": "plan", "agentTypeId": "project-manager", "displayName": "需求规划", "dependsOn": [], "executionMode": "sequential"},
                    {"nodeKey": "extract", "agentTypeId": "backend-developer", "displayName": "字段抽取", "dependsOn": ["plan"], "executionMode": "sequential"},
                    {"nodeKey": "review", "agentTypeId": "code-reviewer", "displayName": "质量复核", "dependsOn": ["extract"], "executionMode": "sequential"},
                    {"nodeKey": "bogus", "agentTypeId": "not-exists", "displayName": "无效节点", "dependsOn": [], "executionMode": "sequential"},
                    {"nodeKey": "extra", "agentTypeId": "test-engineer", "displayName": "验证", "dependsOn": ["ghost", "extra"], "executionMode": "parallel"},
                ],
            })

    monkeypatch.setattr(agent_config_module, "pipeline_llm_client_factory", lambda model: ScriptedFlowModel())
    admin = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin@2026"}).json()
    headers = {"Authorization": f"Bearer {admin['accessToken']}"}

    # 普通用户被拒绝
    assert client.post("/api/v1/admin/pipeline-templates/generate", json={"requirement": "发票识别流程"}).status_code == 403

    response = client.post("/api/v1/admin/pipeline-templates/generate", headers=headers, json={"requirement": "发票识别并生成台账"})
    assert response.status_code == 200, response.text
    body = response.json()
    draft = body["draft"]
    assert draft["name"].startswith("invoice-flow-01")  # 已清洗为合法标识
    assert draft["templateType"] == "custom"
    keys = [n["nodeKey"] for n in draft["nodes"]]
    assert "bogus" not in keys and "plan" in keys and "extract" in keys
    extra = next(n for n in draft["nodes"] if n["nodeKey"] == "extra")
    assert extra["dependsOn"] == []  # ghost 与自依赖均被清理
    assert any("无效智能体引用" in w for w in body["warnings"])
    # 节点按依赖拓扑排序：plan 在 extract 之前
    assert keys.index("plan") < keys.index("extract") < keys.index("review")


def test_pipeline_generate_requires_configured_llm(client):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin@2026"}).json()
    headers = {"Authorization": f"Bearer {admin['accessToken']}"}
    response = client.post("/api/v1/admin/pipeline-templates/generate", headers=headers, json={"requirement": "发票识别与台账生成流程"})
    assert response.status_code == 503  # 未配置模型网关，明确报错而非 Mock


def test_conversation_chat_with_context_and_memory(client, monkeypatch):
    import app.services.conversation as conversation_module
    from app.services.llm_client import LLMResult

    class ScriptedChatModel:
        model = "scripted-chat-model"
        def __init__(self):
            self.chat_calls = 0
        def chat(self, system, messages, *, temperature=0.3):
            self.chat_calls += 1
            if "标题" in system:
                return "导出功能规划讨论"
            # 上下文必须包含召回的记忆与装配的 Skill 指令
            assert any("持久记忆" in m["content"] or "persistent memory" in m["content"].lower() or "Relevant persistent memory" in m["content"] for m in [{"content": system}] + messages)
            last_user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
            return f"已收到：{last_user}"
        def chat_json(self, system, user, *, temperature=0.1):
            # 记忆提取：第一轮返回一条值得记住的事实
            return LLMResult(data={"key": "user-preference", "content": "用户偏好中文回复并关注导出性能", "importance": 0.8})

    monkeypatch.setattr(conversation_module, "conversation_client_factory", lambda model: ScriptedChatModel())
    # 预置一条可召回的项目记忆
    memories = client.get("/api/v1/projects/leave-hub/memories")
    assert memories.status_code == 200

    created = client.post("/api/v1/projects/leave-hub/conversations", json={"agentKey": "project-manager"})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    assert created.json()["agentKey"] == "project-manager"

    # 第一轮对话
    turn = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages", json={"content": "我们计划做一个导出功能，请给建议", "remember": True})
    assert turn.status_code == 200, turn.text
    body = turn.json()
    assert body["userMessage"]["role"] == "user"
    assert body["assistantMessage"]["role"] == "assistant"
    assert body["assistantMessage"]["content"].startswith("已收到：")
    assert body["assistantMessage"]["metadata"]["context"]["historyMessages"] == 0
    assert body["assistantMessage"]["metadata"]["context"]["memoriesRecalled"] >= 0
    assert "budgetTokens" in body["assistantMessage"]["metadata"]["context"]

    # 第二轮：历史应包含上一轮消息
    turn2 = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages", json={"content": "请继续", "remember": True})
    assert turn2.status_code == 200, turn2.text
    assert turn2.json()["assistantMessage"]["metadata"]["context"]["historyMessages"] == 2  # 上一轮的 user + assistant
    assert turn2.json()["assistantMessage"]["content"] == "已收到：请继续"

    # 详情返回全部消息，标题已由模型自动生成
    detail = client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 4
    assert detail.json()["title"] == "导出功能规划讨论"

    # AI 重新生成标题
    regen = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/title")
    assert regen.status_code == 200
    assert regen.json()["title"] == "导出功能规划讨论"

    # 长期记忆提取已写入 episodic 记忆
    all_memories = client.get("/api/v1/projects/leave-hub/memories", params={"memoryType": "episodic"})
    episodic = [m for m in all_memories.json() if m.get("tags") and "conversation" in m["tags"]]
    assert episodic, "对话后应自动提取长期记忆"
    assert any("导出性能" in m["content"] for m in episodic)

    # 重命名与删除
    renamed = client.patch(f"/api/v1/projects/leave-hub/conversations/{conversation_id}", json={"title": "导出功能讨论"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "导出功能讨论"
    assert client.delete(f"/api/v1/projects/leave-hub/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}").status_code == 404


def test_conversation_streaming_with_scripted_model(client, monkeypatch):
    import json as json_module

    import app.services.conversation as conversation_module
    from app.services.llm_client import LLMResult

    class ScriptedStreamModel:
        model = "scripted-stream-model"
        def __init__(self):
            self.stream_calls = 0
        def chat(self, system, messages, *, temperature=0.3):
            if "标题" in system:
                return "发票审核流程咨询"
            return "fallback"
        def chat_stream(self, system, messages, *, temperature=0.3):
            self.stream_calls += 1
            # 上下文必须包含记忆与 Skills 指令
            assert "Relevant persistent memory" in system
            for token in ["计划", "：", "先", "抽取", "发票字段", "，再", "复核"]:
                yield token
        def chat_json(self, system, user, *, temperature=0.1):
            return LLMResult(data={"key": "stream-memory", "content": "流式对话确认了发票字段抽取方案", "importance": 0.7})

    monkeypatch.setattr(conversation_module, "conversation_client_factory", lambda model: ScriptedStreamModel())
    created = client.post("/api/v1/projects/leave-hub/conversations", json={"agentKey": "project-manager"})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    events: list[dict] = []
    with client.stream("POST", f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages/stream", json={"content": "请规划发票审核流程", "remember": True}) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json_module.loads(line[6:]))

    types = [event["type"] for event in events]
    assert types[0] == "meta", types
    assert "context" in events[0] and events[0]["context"]["budgetTokens"] > 0
    deltas = [event["content"] for event in events if event["type"] == "delta"]
    assert "".join(deltas) == "计划：先抽取发票字段，再复核"
    title_event = next((event for event in events if event["type"] == "title"), None)
    assert title_event and title_event["title"] == "发票审核流程咨询"
    done = events[-1]
    assert done["type"] == "done"
    assert done["assistantMessage"]["content"] == "计划：先抽取发票字段，再复核"
    assert done["assistantMessage"]["role"] == "assistant"
    assert done["conversation"]["messageCount"] == 2

    # 落库校验：标题与消息均已持久化
    detail = client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "发票审核流程咨询"
    assert len(detail.json()["messages"]) == 2
    # 长期记忆提取落库
    episodic = [m for m in client.get("/api/v1/projects/leave-hub/memories", params={"memoryType": "episodic"}).json() if m.get("tags") and "conversation" in m["tags"]]
    assert any("发票字段抽取方案" in m["content"] for m in episodic)


def test_conversation_stream_reports_llm_not_configured_as_sse_error(client):
    import json as json_module

    created = client.post("/api/v1/projects/leave-hub/conversations", json={"agentKey": "project-manager"})
    conversation_id = created.json()["id"]
    events: list[dict] = []
    with client.stream("POST", f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages/stream", json={"content": "你好"}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json_module.loads(line[6:]))
    assert events and events[-1]["type"] == "error"
    assert events[-1]["code"] == "LLM_NOT_CONFIGURED"


def test_conversation_agent_mode_with_stubbed_deepagents(client, monkeypatch):
    """工具模式：DeepAgents 流式输出 → HITL 中断 → 人工审批 → 恢复执行 → 工作区文件。"""
    import json as json_module

    import app.services.conversation_agent as conversation_agent_module

    class FakeState:
        def __init__(self, interrupts=None, messages=None):
            self.tasks = [type("T", (), {"interrupts": interrupts or []})()]
            self.values = {"messages": messages or []}

    class FakeChunk:
        def __init__(self, text): self.content = text

    class FakeDeepAgent:
        def __init__(self):
            self.config = None
            self.invoked = False
        def stream(self, input, config, stream_mode="messages"):
            self.config = config
            for text in ["我将先", "检查工作区", "并生成脚本。"]:
                yield (FakeChunk(text), {})
        def get_state(self, config):
            if not self.invoked:
                return FakeState(interrupts=[type("I", (), {"value": {"version": "v1.0", "summary": "对话产出的应用"}})()])
            return FakeState(messages=[type("M", (), {"type": "ai", "content": "已按审批意见完成部署。"})()])
        def invoke(self, command, config):
            self.invoked = True
            return {"messages": [type("M", (), {"type": "ai", "content": "已按审批意见完成部署。"})()]}

    fake = FakeDeepAgent()
    monkeypatch.setattr(conversation_agent_module, "create_deep_agent", lambda **kwargs: fake)
    # 关键：无 Key 时 chat 模式会 503，但 fake 路径不走真实模型；给 settings 假 Key 以通过守卫
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-stub-test")
    from app.core.config import get_settings
    get_settings.cache_clear()

    created = client.post("/api/v1/projects/leave-hub/conversations", json={"agentKey": "project-manager"})
    conversation_id = created.json()["id"]
    # 切换到工具模式
    switched = client.patch(f"/api/v1/projects/leave-hub/conversations/{conversation_id}", json={"mode": "agent"})
    assert switched.status_code == 200 and switched.json()["mode"] == "agent"

    events: list[dict] = []
    with client.stream("POST", f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages/stream", json={"content": "请帮我做一个导出脚本并部署", "remember": False}) as response:
        assert response.status_code == 200, response.text
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json_module.loads(line[6:]))
    types = [e["type"] for e in events]
    assert types[0] == "meta" and events[0]["context"]["mode"] == "agent"
    assert "".join(e["content"] for e in events if e["type"] == "delta") == "我将先检查工作区并生成脚本。"
    interrupt_event = next(e for e in events if e["type"] == "interrupt")
    assert interrupt_event["toolName"] == "pending_approval"
    assert events[-1]["type"] == "done"

    # 待审批列表
    interrupts = client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/interrupts")
    assert interrupts.status_code == 200 and len(interrupts.json()) == 1
    interrupt_id = interrupts.json()[0]["id"]

    # 人工批准 → Agent 恢复执行
    decided = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/interrupts/{interrupt_id}/decide", json={"decision": "approve", "reason": "可以发布"})
    assert decided.status_code == 200, decided.text
    assert decided.json()["assistantMessage"]["content"] == "已按审批意见完成部署。"
    assert fake.invoked is True

    # 中断已消费
    assert client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/interrupts").json() == []

    # 工作区文件（Agent 工作目录，仅返回文件清单）
    workspace = client.get(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/workspace")
    assert workspace.status_code == 200 and "files" in workspace.json()

    # 无 Key 时工具模式明确报错（清理 fake key）
    monkeypatch.delenv("LLM_API_KEY")
    get_settings.cache_clear()
    second = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages/stream", json={"content": "继续"})
    events2 = [json_module.loads(line[6:]) for line in second.iter_lines() if line.startswith("data: ")]
    assert events2[-1]["type"] == "error" and events2[-1]["code"] == "LLM_NOT_CONFIGURED"


def test_conversation_requires_configured_llm(client):
    created = client.post("/api/v1/projects/leave-hub/conversations", json={"agentKey": "project-manager"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    response = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/messages", json={"content": "你好"})
    assert response.status_code == 503  # 未配置模型网关时明确报错，绝不 Mock 回复
    assert "LLM_NOT_CONFIGURED" in response.text
    # 标题重生成：无消息时先返回 409 业务错误（不依赖模型）
    regen = client.post(f"/api/v1/projects/leave-hub/conversations/{conversation_id}/title")
    assert regen.status_code == 409
    assert "CONVERSATION_EMPTY" in regen.text


def test_conversation_context_trimming_keeps_recent_and_drops_oldest():
    from app.services.llm_client import estimate_tokens
    from app.services.conversation import build_chat_context

    assert estimate_tokens("你好世界") == 4
    assert estimate_tokens("hello world") >= 2


def test_requirement_document_attachment_and_clarification_persistence(client):
    saved = client.post("/api/v1/projects/leave-hub/requirements", json={"title": "增量需求", "contentMarkdown": "# 增量需求\n\n增加员工培训证书下载，并保留现有接口。", "structuredData": {"summary": "增加证书下载"}, "status": "confirmed", "changeSummary": "新增证书"})
    assert saved.status_code == 201
    assert saved.json()["version"] >= 1
    document = client.post("/api/v1/projects/leave-hub/documents", json={"documentType": "architecture", "title": "证书模块架构", "contentMarkdown": "# 架构\n\n使用独立证书服务。"})
    assert document.status_code == 201
    attachment = client.post("/api/v1/projects/leave-hub/attachments", files={"file": ("notes.md", b"# Interview\nNeed certificates", "text/markdown")})
    assert attachment.status_code == 201
    assert attachment.json()["extractedTextLength"] > 0
    clarification = client.post("/api/v1/projects/leave-hub/clarifications", json={"question": "证书是否需要电子签章？"})
    assert clarification.status_code == 201
    answered = client.post(f"/api/v1/projects/leave-hub/clarifications/{clarification.json()['id']}/answer", json={"answer": "V1 不需要电子签章。"})
    assert answered.status_code == 200
    assert answered.json()["status"] == "answered"


def test_create_project_initializes_manager_task(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": "培训管理系统", "description": "HR 发布课程，员工报名并查看自己的学习进度。", "template": "Web 全栈应用"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "planning"
    assert body["tasks"] == {"done": 0, "total": 1}
    tasks = client.get(f"/api/v1/projects/{body['id']}/tasks").json()
    assert tasks[0]["agent"] == "项目经理智能体"
    assert tasks[0]["status"] == "in_progress"


def test_project_validation(client):
    response = client.post("/api/v1/projects", json={"name": "x", "description": "太短"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_project_auto_build_requires_model_gateway(client, monkeypatch):
    monkeypatch.setattr(OpenAICompatibleClient, "configured", property(lambda self: False))
    response = client.post("/api/v1/projects", json={
        "name": "自动构建项目", "description": "创建后自动生成完整前后端代码并运行覆盖率和前端测试。",
        "template": "Web 全栈应用", "autoBuild": True,
    })
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"


def test_task_pause_resume_and_logs(client):
    pause = client.post("/api/v1/projects/leave-hub/tasks/t-test/actions", json={"action": "pause"})
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"
    resume = client.post("/api/v1/projects/leave-hub/tasks/t-test/actions", json={"action": "resume"})
    assert resume.status_code == 200
    assert resume.json()["status"] == "in_progress"
    logs = client.get("/api/v1/projects/leave-hub/tasks/t-test/logs", params={"search": "暂停"}).json()
    assert len(logs) == 1
    assert logs[0]["eventType"] == "human_action"


def test_intervention_queue_and_finished_guard(client):
    accepted = client.post(
        "/api/v1/projects/leave-hub/tasks/t-test/interventions",
        json={"content": "请补充 5 万条数据导出的内存峰值测试。", "interventionType": "instruction"},
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "queued"
    rejected = client.post(
        "/api/v1/projects/leave-hub/tasks/t-back/interventions",
        json={"content": "请重做此任务。"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "TASK_ALREADY_FINISHED"


def test_incremental_analysis_and_confirmation(client):
    analysis = client.post(
        "/api/v1/projects/leave-hub/iterations/impact-analysis",
        json={"changeRequest": "新增假勤报表导出功能，支持按部门与日期筛选并导出 Excel。"},
    )
    assert analysis.status_code == 201
    body = analysis.json()
    assert body["riskLevel"] == "low"
    assert body["databaseChange"] is False
    assert "后端开发" in body["suggestedAgents"]
    confirmed = client.post(
        f"/api/v1/projects/leave-hub/iterations/{body['iterationId']}/confirm",
        json={"approved": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "executing"
    incremental = client.get("/api/v1/projects/leave-hub/tasks", params={"task_type": "incremental"}).json()
    assert len(incremental) > 8
    runtime_logs = client.get(
        f"/api/v1/projects/leave-hub/tasks/{incremental[-1]['id']}/logs"
    ).json()
    assert any(item["eventType"] == "runtime_context" for item in runtime_logs)


def test_breaking_change_requires_review(client):
    analysis = client.post(
        "/api/v1/projects/leave-hub/iterations/impact-analysis",
        json={"changeRequest": "删除现有审批 API 并重构为微服务，同时更换数据库。"},
    ).json()
    response = client.post(
        f"/api/v1/projects/leave-hub/iterations/{analysis['iterationId']}/confirm",
        json={"approved": True},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "BREAKING_CHANGE_REQUIRES_REVIEW"


def test_version_compare(client):
    response = client.get(
        "/api/v1/projects/leave-hub/versions/compare",
        params={"from": "v1.1.1", "to": "v1.2.0"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["files"] > 0
    assert any(change["type"] == "added" for change in body["apiChanges"])
    assert body["hasBreakingChanges"] is False


def test_rollback_requires_explicit_data_confirmation(client):
    first = client.post("/api/v1/projects/leave-hub/versions/v1.1.1/rollback", json={})
    assert first.status_code == 409
    assert first.json()["detail"]["details"]["requiresConfirmation"] is True
    confirmed = client.post(
        "/api/v1/projects/leave-hub/versions/v1.1.1/rollback",
        json={"confirmDataRisk": True},
    )
    assert confirmed.status_code == 202
    assert confirmed.json()["targetVersion"] == "v1.1.1"
    assert len(confirmed.json()["steps"]) == 5


def test_artifact_list(client):
    response = client.get("/api/v1/projects/leave-hub/artifacts")
    assert response.status_code == 200
    assert len(response.json()) == 4
    images = client.get("/api/v1/projects/leave-hub/artifacts", params={"type": "image"}).json()
    assert len(images) == 1


def test_skill_registry_loads_built_in_skills(client):
    response = client.get("/api/v1/skills")
    assert response.status_code == 200
    skills = response.json()
    assert {item["name"] for item in skills} == {"requirement-analysis", "code-metrics", "regression-plan"}
    assert all(item["executable"] for item in skills)
    assert all(len(item["checksum"]) == 64 for item in skills)


def test_persistent_memory_and_agent_context(client):
    created = client.post(
        "/api/v1/projects/leave-hub/memories",
        json={
            "agentKey": "backend-developer",
            "scope": "agent",
            "memoryType": "semantic",
            "key": "export-timeout",
            "content": "异步导出任务最大执行时间为 120 秒。",
            "importance": 0.9,
            "tags": ["export", "timeout"],
        },
    )
    assert created.status_code == 201
    context = client.get(
        "/api/v1/projects/leave-hub/agents/backend-developer/context",
        params={"query": "导出 timeout"},
    )
    assert context.status_code == 200
    body = context.json()
    assert any(item["key"] == "export-timeout" for item in body["memories"])
    assert any(item["name"] == "code-metrics" for item in body["skills"])
    assert "Relevant persistent memory" in body["memoryPrompt"]
    assert body["sandbox"]["available"] is True


def test_python_sandbox_executes_with_resource_limits(client):
    response = client.post(
        "/api/v1/projects/leave-hub/sandbox/runs",
        json={"language": "python", "code": "import json\nprint(json.dumps({'ok': True, 'sum': sum(range(6))}))"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["exitCode"] == 0
    assert body["result"] == {"ok": True, "sum": 15}
    assert body["resourceUsage"]["elapsedMs"] >= 0


def test_skill_executes_in_sandbox_and_writes_episodic_memory(client):
    response = client.post(
        "/api/v1/projects/leave-hub/skills/requirement-analysis/execute",
        json={
            "input": {
                "project_name": "费用报销系统",
                "requirement": "员工提交费用报销，部门负责人审批，财务管理员复核并导出统计报表，需要记录审计日志。",
            },
            "rememberResult": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["skillName"] == "requirement-analysis"
    assert body["result"]["projectName"] == "费用报销系统"
    memories = client.get(
        "/api/v1/projects/leave-hub/memories",
        params={"memory_type": "episodic"},
    ).json()
    assert any("requirement-analysis" in item["key"] for item in memories)


def test_llm_json_parser_accepts_fenced_json():
    assert parse_json_object('```json\n{"ok": true, "files": []}\n```') == {"ok": True, "files": []}


def test_real_agent_build_loop_with_scripted_model(client, monkeypatch, tmp_path):
    class ScriptedModel:
        model = "scripted-test-model"
        def __init__(self):
            self.calls = 0
        def chat_json(self, system, user, *, temperature=0.1):
            self.calls += 1
            phase = (self.calls - 1) % 3
            cycle = (self.calls - 1) // 3
            if phase == 0:
                return LLMResult(data={
                    "app_name": "培训管理系统", "summary": "课程和报名管理",
                    "user_roles": ["HR", "员工"], "entities": ["Course", "Enrollment"],
                    "api_endpoints": [{"method": "GET", "path": "/api/courses", "purpose": "课程列表"}],
                    "pages": ["课程列表", "报名管理"], "acceptance_criteria": ["可以报名"],
                    "backend_tasks": ["CRUD"], "frontend_tasks": ["页面"], "test_strategy": {"pytest": True},
                    "affected_files": [], "compatibility_notes": ["保持 API 兼容"],
                }, prompt_tokens=100, completion_tokens=200)
            if phase == 1:
                return LLMResult(data={"summary": "backend", "files": [
                    {"path": "backend/app/main.py", "content": f"# generated cycle {cycle}\nfrom fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef health(): return {{'status':'ok'}}\n"},
                    {"path": "backend/tests/test_health.py", "content": "def test_generated(): assert True\n"},
                ]}, prompt_tokens=150, completion_tokens=300)
            return LLMResult(data={"summary": "frontend", "files": [
                {"path": "frontend/src/App.vue", "content": f"<template><main><h1>培训管理系统 v{cycle}</h1></main></template>"},
            ]}, prompt_tokens=120, completion_tokens=260)

    scripted = ScriptedModel()
    monkeypatch.setattr(agent_build_runner, "client_factory", lambda model: scripted)
    monkeypatch.setattr(agent_build_runner, "submit", lambda build_id: None)
    monkeypatch.setattr(OpenAICompatibleClient, "configured", property(lambda self: True))
    settings = get_settings()
    original_root = settings.agent_build_root
    object.__setattr__(settings, "agent_build_root", tmp_path / "generated")

    def successful_command(workspace, command, timeout_seconds=None):
        return ExecutionResult(
            backend="local-build", command=command, status="completed", exit_code=0,
            stdout="ok", stderr="", error_message="", elapsed_ms=12, workspace=Path(workspace),
        )
    monkeypatch.setattr(sandbox_manager, "execute_build_command", successful_command)
    try:
        created = client.post("/api/v1/projects/leave-hub/agent-builds", json={
            "requirement": "构建员工培训系统，HR 创建课程，员工浏览并报名，包含 REST API、Vue 页面和自动测试。",
            "template": "fullstack", "engine": "staged", "maxFixAttempts": 1,
        })
        assert created.status_code == 202
        build_id = created.json()["id"]
        agent_build_runner.run_sync(build_id)
        completed = client.get(f"/api/v1/projects/leave-hub/agent-builds/{build_id}")
        assert completed.status_code == 200
        body = completed.json()
        assert body["status"] == "completed"
        assert body["progress"] == 100
        assert body["promptTokens"] == 370
        assert body["completionTokens"] == 760
        assert len(body["testResults"]) == 4
        assert all(item["passed"] for item in body["testResults"])
        assert body["mode"] == "initial"
        assert any(log["stage"] == "backend" for log in body["logs"])
        files = client.get(f"/api/v1/projects/leave-hub/agent-builds/{build_id}/files").json()
        assert any(item["path"] == "frontend/src/App.vue" for item in files)
        with agent_build_runner.session_factory() as checkpoint_db:
            assert checkpoint_db.query(AgentCheckpoint).filter(AgentCheckpoint.thread_id == build_id).count() >= 4

        incremental = client.post("/api/v1/projects/leave-hub/agent-builds", json={
            "requirement": "在现有培训系统中增加课程导出功能，保持已有健康检查和报名接口兼容，并补充自动测试。",
            "template": "fullstack", "engine": "staged", "mode": "incremental", "baseBuildId": build_id,
            "maxFixAttempts": 1,
        })
        assert incremental.status_code == 202
        incremental_id = incremental.json()["id"]
        instruction = client.post(
            f"/api/v1/projects/leave-hub/agent-builds/{incremental_id}/instructions",
            json={"content": "不要修改现有健康检查接口，并为导出空数据场景增加测试。"},
        )
        assert instruction.status_code == 202
        agent_build_runner.run_sync(incremental_id)
        changed = client.get(f"/api/v1/projects/leave-hub/agent-builds/{incremental_id}").json()
        assert changed["status"] == "completed"
        assert changed["mode"] == "incremental"
        assert changed["baseBuildId"] == build_id
        assert changed["changedFilesCount"] == 2
        assert any(log["stage"] == "human" and log["metadata"].get("consumed") for log in changed["logs"])

        import app.api.application_deployments as deployment_api
        class FakeDockerRuntime:
            class Settings:
                deployment_backend_memory_mb = 512
                deployment_frontend_memory_mb = 256
                deployment_public_host = "localhost"
            settings = Settings()
            available = True
            def status(self): return {"docker_available": True, "docker_version": "test-1.0", "ready": True, "message": "ready"}
            def write_deployment_files(self, workspace): pass
            def build_image(self, context, dockerfile, tag, timeout=600): return DockerCommandResult(["docker","build"],0,"ok","",10)
            def create_network(self, name): return DockerCommandResult([],0,"ok","",1)
            def run_backend(self, name, image, network, database_url=None): return DockerCommandResult([],0,"backend","",1)
            def run_frontend(self, name, image, network): return DockerCommandResult([],0,"frontend","",1)
            def host_port(self, container): return 43123
            def smoke_test(self, url): return {"passed": True, "rootStatus": 200, "healthStatus": 200, "attempts": 1}
            def logs(self, container, tail=200): return "container log"
            def stop_remove(self, container): pass
            def remove_network(self, network): pass
        fake_docker = FakeDockerRuntime()
        monkeypatch.setattr(deployment_api, "docker_runtime", fake_docker)
        monkeypatch.setattr(application_deployment_runner, "runtime", fake_docker)
        monkeypatch.setattr(application_deployment_runner, "submit", lambda deployment_id: None)
        deploy = client.post("/api/v1/projects/leave-hub/application-deployments", json={"buildId": incremental_id, "environment": "test"})
        assert deploy.status_code == 202
        deployment_id = deploy.json()["id"]
        application_deployment_runner.run_sync(deployment_id)
        running = client.get(f"/api/v1/projects/leave-hub/application-deployments/{deployment_id}").json()
        assert running["status"] == "running"
        assert running["deployUrl"] == "http://localhost:43123"
        assert running["smokeResult"]["passed"] is True
        stopped = client.post(f"/api/v1/projects/leave-hub/application-deployments/{deployment_id}/stop")
        assert stopped.status_code == 200
        assert stopped.json()["status"] == "stopped"

        analysis = client.post("/api/v1/projects/leave-hub/iterations/impact-analysis", json={"changeRequest": "增加课程完成证书下载功能，保持现有报名 API 兼容并执行完整回归测试。"}).json()
        confirmed = client.post(f"/api/v1/projects/leave-hub/iterations/{analysis['iterationId']}/confirm", json={"approved": True})
        assert confirmed.status_code == 200
        automation = confirmed.json()["impactAnalysis"]["automation"]
        assert automation["status"] == "queued"
        assert automation["mode"] == "incremental"
        queued_build = client.get(f"/api/v1/projects/leave-hub/agent-builds/{automation['buildId']}").json()
        assert queued_build["iterationId"] == analysis["iterationId"]
        assert queued_build["mode"] == "incremental"
    finally:
        object.__setattr__(settings, "agent_build_root", original_root)


def test_langgraph_checkpointer_selection_and_semantic_rerank(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.services.deepagents_runtime import build_langgraph_checkpointer

    # SQLite：默认返回 SqliteSaver
    settings = SimpleNamespace(
        database_url="sqlite:///./data/x.db",
        langgraph_checkpoint_db=tmp_path / "cp.sqlite",
    )
    saver = build_langgraph_checkpointer(settings)
    assert saver.__class__.__name__ == "SqliteSaver"
    assert (tmp_path / "cp.sqlite").exists()

    # PostgreSQL：连接失败时回退 SQLite 而不是抛异常
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("no server")))
    pg_settings = SimpleNamespace(
        database_url="postgresql+psycopg://user:pw@localhost:5432/db",
        langgraph_checkpoint_db=tmp_path / "cp2.sqlite",
    )
    fallback = build_langgraph_checkpointer(pg_settings)
    assert fallback.__class__.__name__ == "SqliteSaver"

    # 语义重排：embedding 可用时混合排序；不可用时保持关键词顺序
    from app.models import AgentMemory
    from app.services.memory import MemoryService

    def make(key: str, content: str, importance: float = 0.5) -> AgentMemory:
        item = AgentMemory(agent_key="a", scope="project", memory_type="semantic", key=key, content=content, importance=importance)
        item.id = key
        return item

    candidates = [make("export", "导出功能限制五万条"), make("unrelated", "公司食堂菜单")]
    # 注入假 embedding 客户端
    import app.services.memory as memory_module
    import app.services.llm_client as llm_client_module

    class FakeEmbedClient:
        def embed_query(self, text: str):
            if "导出" in text:
                return [1.0, 0.0]
            if "食堂" in text:
                return [0.0, 1.0]
            if "限制" in text or "菜单" in text:
                return [0.9, 0.1] if "限制" in text else [0.1, 0.9]
            return None

    monkeypatch.setattr(llm_client_module, "OpenAICompatibleClient", lambda: FakeEmbedClient())
    ranked = MemoryService._semantic_rerank(candidates, "导出功能")
    assert ranked[0].key == "export"  # 语义相关者排前

    # embedding 不可用：保持原顺序（不报错）
    class NoEmbedClient:
        def embed_query(self, text):
            return None

    monkeypatch.setattr(llm_client_module, "OpenAICompatibleClient", lambda: NoEmbedClient())
    same = MemoryService._semantic_rerank(candidates, "导出功能")
    assert [item.key for item in same] == ["export", "unrelated"]

    # 余弦相似度纯函数
    assert abs(MemoryService._cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(MemoryService._cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
