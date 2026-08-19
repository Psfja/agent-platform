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
