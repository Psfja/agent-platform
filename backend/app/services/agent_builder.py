from __future__ import annotations

import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database import SessionLocal
from app.models import AgentBuild, AgentBuildLog, ApplicationDeployment, Artifact, Iteration, Project, ProjectDocument, Task, VersionSnapshot, uuid_str
from app.schemas import MemoryCreate
from app.services.agent_runtime import agent_runtime
from app.services.generated_workspace import GeneratedWorkspace
from app.services.checkpointer import checkpoint_store
from app.services.deepagents_runtime import native_deepagents_runtime
from app.services.llm_client import ChatModel, LLMResult, OpenAICompatibleClient
from app.services.integrations import artifact_storage, git_publisher, notification_service
from app.services.memory import memory_service
from app.services.sandbox import ExecutionResult, sandbox_manager
from app.services.task_queue import persistent_queue

STAGES = {
    "planning": ("architect", "AR", "架构规划与任务拆解"),
    "backend": ("backend-developer", "BE", "生成 FastAPI 后端与测试"),
    "frontend": ("frontend-developer", "FE", "生成 Vue 3 前端应用"),
    "testing": ("test-engineer", "QA", "运行自动测试与构建"),
}


class BuildCancelled(Exception):
    pass


class AgentBuildRunner:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="agent-build")
        self.session_factory = SessionLocal
        self.client_factory: Callable[[str], ChatModel] = lambda model: OpenAICompatibleClient(model=model)

    def submit(self, build_id: str) -> None:
        persistent_queue.enqueue("agent_build", {"build_id": build_id}, fallback=lambda: self.run_sync(build_id), priority=5)

    def create_tasks(self, db: Session, build: AgentBuild) -> None:
        root_id = f"build-task-{uuid_str()}"
        root = Task(
            id=root_id, project_id=build.project_id, iteration_id=build.iteration_id,
            name="真实 Agent 全栈构建", agent_type="项目经理智能体", agent_short="PM",
            description=build.requirement, status="in_progress", progress=1, task_type="incremental",
            current_action="准备 Agent 运行时", started_at=datetime.now(timezone.utc),
            thread_id=f"agent-build:{build.id}:root",
            execution_metadata={"agentBuildId": build.id, "realExecution": True},
        )
        db.add(root)
        db.flush()
        for stage, (agent_key, short, title) in STAGES.items():
            db.add(Task(
                id=f"build-task-{uuid_str()}", project_id=build.project_id,
                iteration_id=build.iteration_id, parent_task_id=root_id, name=title,
                agent_type=f"{agent_key} Agent", agent_short=short, description=title,
                status="pending", progress=0, task_type="incremental",
                thread_id=f"agent-build:{build.id}:{stage}",
                execution_metadata={"agentBuildId": build.id, "stage": stage, "realExecution": True},
            ))

    def run_sync(self, build_id: str) -> None:
        with self.session_factory() as db:
            build = db.get(AgentBuild, build_id)
            if not build:
                return
            workspace = GeneratedWorkspace(build.project_id, build.id)
            client = self.client_factory(build.model)
            checkpoint = checkpoint_store.latest(db, build.id)
            resume_stage = checkpoint.stage if checkpoint and workspace.root.is_dir() else ""
            try:
                build.status = "running"
                build.current_stage = "initializing"
                build.progress = 2
                build.started_at = datetime.now(timezone.utc)
                build.workspace_path = str(workspace.root)
                self._log(db, build, "initializing", "info", "project-manager", "创建隔离项目工作区并加载 Agent 运行时。")
                self._update_root_task(db, build, "正在初始化生成工作区", 2)
                db.commit()

                meta = dict((build.plan or {}).get("_meta", {}))
                if resume_stage:
                    before_manifest = dict(checkpoint.state.get("beforeManifest", {})) or workspace.manifest()
                    self._log(db, build, "resuming", "warning", "project-manager", f"从持久 Checkpoint v{checkpoint.version} 恢复，最后完成阶段：{resume_stage}。")
                else:
                    if meta.get("mode") == "incremental":
                        base = db.get(AgentBuild, meta.get("baseBuildId"))
                        if not base or base.status != "completed":
                            raise AppError(422, "BASE_BUILD_NOT_READY", "增量构建基础版本不可用")
                        workspace.initialize_from(Path(base.workspace_path))
                        self._log(db, build, "initializing", "info", "project-manager", f"已加载基础构建 {base.id[-8:]} 的现有源码，后续仅修改受影响文件。")
                    else:
                        workspace.initialize_fullstack()
                    before_manifest = workspace.manifest()
                    checkpoint_store.save(db, build.id, build.id, "initialized", {"beforeManifest": before_manifest, "workspace": str(workspace.root)})
                    db.commit()
                self._check_cancel(db, build)

                if meta.get("engine") == "deepagents" and resume_stage not in {"frontend", "testing", "completed"}:
                    decision = meta.pop("hitlDecision", None)
                    outcome = native_deepagents_runtime.invoke(db, build.project_id, build.id, workspace.root, build.requirement, decision)
                    if outcome.status == "waiting_approval":
                        build.status = "waiting_approval"
                        build.current_stage = "hitl"
                        build.plan = {**(build.plan or {}), "_meta": {**meta, "hitlInterrupt": outcome.interrupt}}
                        self._log(db, build, "hitl", "warning", "project-manager", "DeepAgents 在敏感工具调用前暂停，等待人工审批。", {"interrupt": outcome.interrupt})
                        checkpoint_store.save(db, build.id, build.id, "hitl", {"beforeManifest": before_manifest, "interrupt": outcome.interrupt})
                        db.commit()
                        return
                    build.plan = {**(build.plan or {}), "deepagents": {"status": "completed", "messageCount": len(outcome.result.get("messages", []))}, "_meta": meta}
                    for stage in ["planning", "backend", "frontend"]:
                        self._complete_stage_task(db, build, stage, "completed", 100, "由原生 DeepAgents SubAgent 完成。")
                    checkpoint_store.save(db, build.id, build.id, "frontend", {"beforeManifest": before_manifest, "files": workspace.manifest(), "engine": "deepagents"})
                    db.commit()
                    resume_stage = "frontend"

                completed_stages = {"planning": 1, "backend": 2, "frontend": 3, "testing": 4, "completed": 5}
                resume_rank = completed_stages.get(resume_stage, 0)
                if resume_rank < 1:
                    plan_result = self._plan(db, build, client, workspace)
                    build.plan = {**plan_result.data, "_meta": {**meta, **(build.plan or {}).get("_meta", {})}}
                    self._add_usage(build, plan_result)
                    self._complete_stage_task(db, build, "planning", "completed", 100, "架构方案与验收标准已生成。")
                    checkpoint_store.save(db, build.id, build.id, "planning", {"beforeManifest": before_manifest, "plan": build.plan})
                    db.commit()
                else:
                    self._log(db, build, "resuming", "info", "architect", "跳过已完成的架构规划阶段。")

                if resume_rank < 2:
                    backend_result = self._generate_backend(db, build, client, workspace)
                    written = workspace.apply_bundle(backend_result.data, allowed_prefix="backend")
                    self._add_usage(build, backend_result)
                    self._log(db, build, "backend", "success", "backend-developer", f"后端 Agent 写入 {len(written)} 个文件。", {"files": [item["path"] for item in written]})
                    self._complete_stage_task(db, build, "backend", "completed", 100, f"生成 {len(written)} 个后端文件。")
                    checkpoint_store.save(db, build.id, build.id, "backend", {"beforeManifest": before_manifest, "files": workspace.manifest()})
                    db.commit()
                    self._check_cancel(db, build)
                else:
                    self._log(db, build, "resuming", "info", "backend-developer", "跳过已完成的后端生成阶段。")

                if resume_rank < 3:
                    frontend_result = self._generate_frontend(db, build, client, workspace)
                    written = workspace.apply_bundle(frontend_result.data, allowed_prefix="frontend")
                    self._add_usage(build, frontend_result)
                    self._log(db, build, "frontend", "success", "frontend-developer", f"前端 Agent 写入 {len(written)} 个文件。", {"files": [item["path"] for item in written]})
                    self._complete_stage_task(db, build, "frontend", "completed", 100, f"生成 {len(written)} 个前端文件。")
                    checkpoint_store.save(db, build.id, build.id, "frontend", {"beforeManifest": before_manifest, "files": workspace.manifest()})
                    db.commit()
                    self._check_cancel(db, build)
                else:
                    self._log(db, build, "resuming", "info", "frontend-developer", "跳过已完成的前端生成阶段。")

                passed = False
                for attempt in range(build.max_fix_attempts + 1):
                    build.attempt = attempt
                    results = self._run_tests(db, build, workspace)
                    build.test_results = [*build.test_results, *results]
                    passed = all(item["passed"] for item in results)
                    db.commit()
                    if passed:
                        break
                    if attempt >= build.max_fix_attempts:
                        break
                    self._check_cancel(db, build)
                    fix_result = self._repair(db, build, client, workspace, results, attempt + 1)
                    fixed = workspace.apply_bundle(fix_result.data)
                    self._add_usage(build, fix_result)
                    self._log(db, build, "fixing", "info", "code-reviewer", f"自动修复第 {attempt + 1} 轮：更新 {len(fixed)} 个文件。", {"files": [item["path"] for item in fixed]})
                    db.commit()

                if not passed:
                    self._complete_stage_task(db, build, "testing", "failed", 100, "自动测试在修复次数耗尽后仍未通过。")
                    raise AppError(422, "AUTOMATED_TESTS_FAILED", "生成项目未通过自动测试", {"attempts": build.attempt + 1})

                self._complete_stage_task(db, build, "testing", "completed", 100, "后端覆盖率、前端单测与生产构建全部通过。")
                build.generated_files = workspace.list_files()
                diff = workspace.diff_manifests(before_manifest, workspace.manifest())
                build.plan = {**build.plan, "_meta": {**build.plan.get("_meta", {}), "changedFilesCount": sum(len(items) for items in diff.values()), "fileDiff": diff}}
                archive = workspace.create_archive()
                build.artifact_path = str(archive)
                storage_meta = artifact_storage.upload(archive, f"projects/{build.project_id}/builds/{build.id}.zip")
                try:
                    git_meta = git_publisher.publish(workspace.root, f"build/{build.id[-8:]}", f"feat(agent): {build.requirement[:72]}")
                except Exception as git_error:
                    git_meta = {"error": str(git_error)}
                build.plan = {**build.plan, "_meta": {**build.plan.get("_meta", {}), "artifactStorage": storage_meta, "git": git_meta}}
                build.status = "completed"
                build.current_stage = "completed"
                build.progress = 100
                build.finished_at = datetime.now(timezone.utc)
                self._update_root_task(db, build, "全栈应用生成并通过自动测试", 100, completed=True)
                self._log(db, build, "completed", "success", "project-manager", f"真实 Agent 构建完成：{len(build.generated_files)} 个源码文件，全部质量门禁通过。")
                checkpoint_store.save(db, build.id, build.id, "completed", {"beforeManifest": before_manifest, "artifactPath": str(archive), "fileDiff": diff, "progress": 100})
                db.add(Artifact(
                    project_id=build.project_id, iteration_id=build.iteration_id,
                    name=f"Agent Build {build.id[-8:]}", artifact_type="generated_app",
                    path=str(archive), size_bytes=archive.stat().st_size,
                    metadata_json={"buildId": build.id, "model": build.model, "testsPassed": True},
                ))
                memory_service.create(db, build.project_id, MemoryCreate(
                    agent_key="project-manager", scope="project", memory_type="episodic",
                    key=f"agent-build:{build.id[-8:]}",
                    content=f"真实 Agent 已完成全栈生成并通过 pytest 与 Vite build。需求：{build.requirement[:1000]}",
                    importance=0.85, tags=["agent-build", "tests-passed"],
                    metadata={"buildId": build.id, "artifactPath": str(archive), "model": build.model},
                ))
                project = db.get(Project, build.project_id)
                auto_deployment_id: str | None = None
                if project:
                    project.status = "completed"
                    project.progress = 100
                    project.extra_config = {**(project.extra_config or {}), "activeAgentBuildId": None, "lastSuccessfulAgentBuildId": build.id}
                    project.updated_at = datetime.now(timezone.utc)
                    meta = build.plan.get("_meta", {})
                    if meta.get("autoDeploy"):
                        deployment = ApplicationDeployment(
                            id=f"app-deploy-{uuid_str()}", project_id=build.project_id, build_id=build.id,
                            environment=meta.get("deployEnvironment", "test"), version=f"build-{build.id[-8:]}",
                            status="pending", current_stage="queued", progress=0,
                        )
                        db.add(deployment)
                        auto_deployment_id = deployment.id
                        project.status = "deploying"
                        project.extra_config = {**project.extra_config, "deploymentPreviousStatus": "completed", "activeDeploymentId": deployment.id}
                        self._log(db, build, "deployment", "info", "deployment-engineer", f"质量门禁通过，已自动创建 {deployment.environment} 环境部署。", {"deploymentId": deployment.id})
                    self._persist_generated_documents(db, build, workspace)
                    notification_service.notify(db, project, "agent_build.completed", "Agent 构建完成", f"构建 {build.id[-8:]} 已通过全部质量门禁。")
                if build.iteration_id:
                    iteration = db.get(Iteration, build.iteration_id)
                    if iteration:
                        coverage_values = [result.get("coverage") for result in build.test_results if result.get("coverage") is not None]
                        iteration.changed_files_count = build.plan.get("_meta", {}).get("changedFilesCount", 0)
                        iteration.test_pass_rate = 100.0
                        iteration.status = "deploying" if auto_deployment_id else "completed"
                        iteration.deploy_status = "自动部署中" if auto_deployment_id else "构建与回归测试通过"
                        iteration.finished_at = None if auto_deployment_id else datetime.now(timezone.utc)
                        existing_snapshot = db.scalar(select(VersionSnapshot).where(VersionSnapshot.project_id == build.project_id, VersionSnapshot.version == iteration.version))
                        if not existing_snapshot:
                            db.add(VersionSnapshot(
                                project_id=build.project_id, iteration_id=iteration.id, version=iteration.version,
                                code_snapshot_path=str(archive),
                                code_manifest={"files": {file["path"]: {"size": file["size"], "sha256": file["sha256"]} for file in build.generated_files}, "coverage": coverage_values[-1] if coverage_values else None, "fileDiff": build.plan.get("_meta", {}).get("fileDiff", {})},
                                db_schema_snapshot="pending deployment migration snapshot",
                                api_snapshot={"source": "agent-build", "buildId": build.id},
                                docker_image_tag="", deploy_config_snapshot={}, is_current=False,
                            ))
                db.commit()
                if auto_deployment_id:
                    from app.services.application_deployer import application_deployment_runner
                    application_deployment_runner.submit(auto_deployment_id)
            except BuildCancelled:
                build.status = "cancelled"
                build.current_stage = "cancelled"
                build.finished_at = datetime.now(timezone.utc)
                build.error_message = "用户取消构建"
                self._update_root_task(db, build, "构建已取消", build.progress, cancelled=True)
                self._log(db, build, "cancelled", "warning", "project-manager", "用户请求取消，Agent 构建已安全终止。")
                self._restore_project_after_failure(db, build)
                db.commit()
            except Exception as exc:
                db.rollback()
                build = db.get(AgentBuild, build_id)
                if not build:
                    return
                build.status = "failed"
                build.current_stage = "failed"
                build.finished_at = datetime.now(timezone.utc)
                build.error_message = self._error_message(exc)
                self._update_root_task(db, build, f"构建失败：{build.error_message[:120]}", build.progress, failed=True)
                self._log(db, build, "failed", "error", None, build.error_message, {"trace": traceback.format_exc()[-4000:]})
                self._restore_project_after_failure(db, build)
                db.commit()

    def _plan(self, db: Session, build: AgentBuild, client: ChatModel, workspace: GeneratedWorkspace) -> LLMResult:
        incremental = (build.plan or {}).get("_meta", {}).get("mode") == "incremental"
        self._start_stage(db, build, "planning", 10, "架构设计 Agent 正在分析增量影响。" if incremental else "架构设计 Agent 正在拆解需求。")
        context = agent_runtime.build_context(db, build.project_id, "project-manager", build.requirement)
        system = """You are a principal software architect. Return ONLY one JSON object. Design a small but complete Vue 3 + FastAPI application that can be built and tested locally. Do not include markdown fences. Required keys: app_name, summary, user_roles (array), entities (array of objects), api_endpoints (array of objects with method/path/purpose), pages (array), acceptance_criteria (array), backend_tasks (array), frontend_tasks (array), test_strategy (object), affected_files (array), compatibility_notes (array). For incremental work, preserve existing architecture and identify the smallest affected file set. Keep the MVP focused and implementable without external cloud services."""
        existing = workspace.source_snapshot(35_000) if incremental else "(new project)"
        instructions = self._consume_instructions(db, build)
        user = f"""Build mode: {'incremental modification' if incremental else 'new project'}\nProject requirement/change request:\n{build.requirement}\n\nHuman instructions received before planning:\n{instructions or '(none)'}\n\nExisting source snapshot:\n{existing}\n\nPersistent memory:\n{context['memory_prompt']}\n\nLoaded skills:\n{context['skill_prompt']}\n\nTarget stack: Vue 3 JavaScript + Vite frontend; FastAPI + Pydantic backend. Quality gates: backend coverage >=80%, frontend Vitest, and Vite production build."""
        result = client.chat_json(system, user, temperature=0.1)
        required = {"app_name", "api_endpoints", "pages", "acceptance_criteria", "affected_files", "compatibility_notes"}
        if not required.issubset(result.data):
            raise AppError(422, "AGENT_PLAN_INVALID", "架构 Agent 返回的计划缺少必要字段", {"missing": sorted(required - result.data.keys())})
        self._log(db, build, "planning", "success", "architect", f"架构计划已生成：{len(result.data.get('api_endpoints', []))} 个 API，{len(result.data.get('pages', []))} 个页面。")
        return result

    def _generate_backend(self, db: Session, build: AgentBuild, client: ChatModel, workspace: GeneratedWorkspace) -> LLMResult:
        incremental = build.plan.get("_meta", {}).get("mode") == "incremental"
        self._start_stage(db, build, "backend", 30, "后端开发 Agent 正在最小化修改受影响代码。" if incremental else "后端开发 Agent 正在生成 FastAPI 服务和 pytest。")
        context = agent_runtime.build_context(db, build.project_id, "backend-developer", build.requirement)
        system = """You are a senior FastAPI engineer. Return ONLY JSON: {\"summary\": string, \"files\": [{\"path\": string, \"content\": string}]}. Every path MUST start with backend/. Generate a complete runnable backend for the supplied plan. Requirements: Python 3.11+, FastAPI, Pydantic v2, CORS, validation and useful errors. If persistent entities are required, use SQLAlchemy + Alembic with versioned migrations; read DATABASE_URL from the environment and fall back to SQLite only for local tests. Otherwise a deterministic in-memory repository is acceptable. Include at least 5 meaningful pytest tests under backend/tests and target >=80% coverage. In incremental mode return ONLY new or modified files, preserve unaffected code, existing API signatures and stored data. Keep requirements.txt compatible with the approved platform environment. Do not use markdown fences or omit code."""
        instructions = self._consume_instructions(db, build)
        existing = workspace.source_snapshot(60_000) if incremental else "(baseline scaffold only)"
        user = f"""Mode: {'incremental' if incremental else 'initial'}\nRequirement:\n{build.requirement}\n\nArchitecture plan:\n{json.dumps(build.plan, ensure_ascii=False)}\n\nNew human instructions:\n{instructions or '(none)'}\n\nExisting source:\n{existing}\n\nMemory:\n{context['memory_prompt']}\n\nSkills:\n{context['skill_prompt']}\n\nTests run from backend with pytest-cov and must reach 80% coverage."""
        return client.chat_json(system, user, temperature=0.05)

    def _generate_frontend(self, db: Session, build: AgentBuild, client: ChatModel, workspace: GeneratedWorkspace) -> LLMResult:
        incremental = build.plan.get("_meta", {}).get("mode") == "incremental"
        self._start_stage(db, build, "frontend", 50, "前端开发 Agent 正在最小化修改受影响页面。" if incremental else "前端开发 Agent 正在生成 Vue 3 应用。")
        context = agent_runtime.build_context(db, build.project_id, "frontend-developer", build.requirement)
        system = """You are a senior Vue 3 product engineer. Return ONLY JSON: {\"summary\": string, \"files\": [{\"path\": string, \"content\": string}]}. Every path MUST start with frontend/. Generate a polished runnable Vue 3 + Vite JavaScript SPA for the supplied plan. Use the Composition API, semantic HTML and self-contained CSS. Use native fetch with relative /api URLs and configure Vite proxy if needed. Runtime dependencies are restricted to vue; test/dev dependencies to vite, @vitejs/plugin-vue, vitest, @vue/test-utils and jsdom. Include meaningful Vitest component tests and keep test script exactly vitest run. In incremental mode return ONLY new or modified files and preserve unaffected components. Avoid external CDNs, images and fonts. package.json build script MUST be exactly vite build. Do not use markdown fences or omit code."""
        instructions = self._consume_instructions(db, build)
        existing = workspace.source_snapshot(60_000) if incremental else "(baseline scaffold only)"
        user = f"""Mode: {'incremental' if incremental else 'initial'}\nRequirement:\n{build.requirement}\n\nArchitecture plan:\n{json.dumps(build.plan, ensure_ascii=False)}\n\nNew human instructions:\n{instructions or '(none)'}\n\nExisting source:\n{existing}\n\nMemory:\n{context['memory_prompt']}\n\nSkills:\n{context['skill_prompt']}\n\nQuality gates: npm install --ignore-scripts, npm run test, npm run build."""
        return client.chat_json(system, user, temperature=0.1)

    def _run_tests(self, db: Session, build: AgentBuild, workspace: GeneratedWorkspace) -> list[dict[str, Any]]:
        self._start_stage(db, build, "testing", 70 + min(build.attempt * 8, 20), f"测试 Agent 正在执行质量门禁（第 {build.attempt + 1} 轮）。")
        commands = []
        if (workspace.root / "backend" / "alembic.ini").is_file():
            commands.append(("database-migration", workspace.root / "backend", ["python", "-m", "alembic", "upgrade", "head"]))
        commands.extend([
            ("backend-coverage", workspace.root / "backend", ["python", "-m", "pytest", "-q", "--cov=app", "--cov-report=json:coverage.json", "--cov-fail-under=80"]),
            ("frontend-install", workspace.root / "frontend", ["npm", "install", "--no-audit", "--no-fund", "--ignore-scripts"]),
            ("frontend-unit", workspace.root / "frontend", ["npm", "run", "test"]),
            ("frontend-build", workspace.root / "frontend", ["npm", "run", "build"]),
        ])
        results = []
        install_failed = False
        for name, cwd, command in commands:
            if name in {"frontend-unit", "frontend-build"} and install_failed:
                result = {"name": name, "command": command, "passed": False, "status": "skipped", "exitCode": None, "stdout": "", "stderr": "Skipped because npm install failed", "elapsedMs": 0, "attempt": build.attempt}
            else:
                execution = sandbox_manager.execute_build_command(cwd, command)
                result = self._test_result(name, execution, build.attempt)
                if name == "backend-coverage":
                    coverage_path = cwd / "coverage.json"
                    if coverage_path.is_file():
                        try:
                            result["coverage"] = round(float(json.loads(coverage_path.read_text(encoding="utf-8")).get("totals", {}).get("percent_covered", 0)), 2)
                        except (ValueError, json.JSONDecodeError):
                            result["coverage"] = 0.0
                if name == "frontend-install" and not result["passed"]:
                    install_failed = True
            results.append(result)
            level = "success" if result["passed"] else "error"
            suffix = f"，覆盖率 {result['coverage']}%" if result.get("coverage") is not None else ""
            self._log(db, build, "testing", level, "test-engineer", f"{name}: {'通过' if result['passed'] else '失败'} ({result['elapsedMs']} ms){suffix}", {"exitCode": result["exitCode"], "coverage": result.get("coverage"), "stderr": result["stderr"][-1500:]})
        return results

    def _repair(self, db: Session, build: AgentBuild, client: ChatModel, workspace: GeneratedWorkspace, results: list[dict[str, Any]], repair_number: int) -> LLMResult:
        build.current_stage = "fixing"
        build.progress = min(88, 76 + repair_number * 6)
        self._log(db, build, "fixing", "warning", "code-reviewer", f"质量门禁失败，代码审查 Agent 启动第 {repair_number} 轮自动修复。")
        context = agent_runtime.build_context(db, build.project_id, "code-reviewer", "自动修复测试失败")
        failures = [{"name": item["name"], "stdout": item["stdout"][-5000:], "stderr": item["stderr"][-5000:], "exitCode": item["exitCode"]} for item in results if not item["passed"]]
        system = """You are a code repair agent. Return ONLY JSON: {\"summary\": string, \"root_cause\": string, \"files\": [{\"path\": string, \"content\": string}]}. Diagnose the supplied pytest/npm failure and return complete replacement content ONLY for files that must change. Paths must start with backend/ or frontend/. Preserve working functionality. Do not use markdown fences."""
        user = f"""Requirement:\n{build.requirement}\n\nPlan:\n{json.dumps(build.plan, ensure_ascii=False)}\n\nFailed gates:\n{json.dumps(failures, ensure_ascii=False)}\n\nCurrent source files:\n{workspace.source_snapshot()}\n\nRelevant memory and skills:\n{context['memory_prompt']}\n{context['skill_prompt']}"""
        return client.chat_json(system, user, temperature=0.05)

    def _persist_generated_documents(self, db: Session, build: AgentBuild, workspace: GeneratedWorkspace) -> None:
        documents = {
            "architecture": ("架构设计文档", f"# 架构设计\n\n{json.dumps(build.plan, ensure_ascii=False, indent=2)}\n"),
            "api": ("API 接口文档", "# API 接口\n\n" + "\n".join(f"- `{item.get('method','GET')} {item.get('path','/')}` — {item.get('purpose','')}" for item in build.plan.get('api_endpoints', []))),
            "test_report": ("自动测试报告", "# 测试报告\n\n" + "\n".join(f"- {item['name']}: {'通过' if item['passed'] else '失败'}" + (f"，覆盖率 {item['coverage']}%" if item.get('coverage') is not None else "") for item in build.test_results[-10:])),
        }
        readme = workspace.root / "docs" / "README.md"
        if readme.is_file(): documents["deployment"] = ("项目说明与部署文档", readme.read_text(encoding="utf-8", errors="replace"))
        for document_type, (title, content) in documents.items():
            version = (db.scalar(select(func.max(ProjectDocument.version)).where(ProjectDocument.project_id == build.project_id, ProjectDocument.document_type == document_type)) or 0) + 1
            db.add(ProjectDocument(project_id=build.project_id, document_type=document_type, version=version, title=title, content_markdown=content, source_build_id=build.id, metadata_json={"buildId": build.id, "iterationId": build.iteration_id}))

    def _consume_instructions(self, db: Session, build: AgentBuild) -> str:
        logs = db.scalars(
            select(AgentBuildLog).where(
                AgentBuildLog.build_id == build.id,
                AgentBuildLog.stage == "human",
            ).order_by(AgentBuildLog.created_at.asc())
        ).all()
        meta = dict((build.plan or {}).get("_meta", {}))
        accumulated = list(meta.get("humanInstructions", []))
        for log in logs:
            log_meta = dict(log.metadata_json or {})
            if not log_meta.get("consumed"):
                accumulated.append(log.message)
                log_meta.update({"consumed": True, "consumedAt": datetime.now(timezone.utc).isoformat(), "consumedByStage": build.current_stage})
                log.metadata_json = log_meta
                self._log(db, build, build.current_stage, "info", "project-manager", f"已将人工指令注入当前 Agent 上下文：{log.message[:160]}", {"instructionId": log.id})
        # Keep order while preventing repeated prompt injection.
        accumulated = list(dict.fromkeys(accumulated))[-20:]
        build.plan = {**(build.plan or {}), "_meta": {**meta, "humanInstructions": accumulated}}
        return "\n".join(f"- {item}" for item in accumulated)

    def _start_stage(self, db: Session, build: AgentBuild, stage: str, progress: int, message: str) -> None:
        self._check_cancel(db, build)
        build.current_stage = stage
        build.progress = progress
        if build.iteration_id and stage == "testing":
            iteration = db.get(Iteration, build.iteration_id)
            if iteration:
                iteration.status = "testing"; iteration.deploy_status = "执行自动回归测试"
        self._set_stage_task(db, build, stage, "in_progress", max(3, progress), message)
        self._update_root_task(db, build, message, progress)
        self._log(db, build, stage, "info", STAGES.get(stage, (None,))[0], message)
        db.flush()

    def _set_stage_task(self, db: Session, build: AgentBuild, stage: str, status: str, progress: int, action: str) -> None:
        task = db.scalar(select(Task).where(Task.thread_id == f"agent-build:{build.id}:{stage}"))
        if task:
            task.status = status
            task.progress = min(100, progress)
            task.current_action = action
            if status == "in_progress" and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            if status in {"completed", "failed", "cancelled"}:
                task.finished_at = datetime.now(timezone.utc)

    def _complete_stage_task(self, db: Session, build: AgentBuild, stage: str, status: str, progress: int, summary: str) -> None:
        self._set_stage_task(db, build, stage, status, progress, summary)
        task = db.scalar(select(Task).where(Task.thread_id == f"agent-build:{build.id}:{stage}"))
        if task:
            task.result_summary = summary

    def _update_root_task(self, db: Session, build: AgentBuild, action: str, progress: int, completed: bool = False, failed: bool = False, cancelled: bool = False) -> None:
        task = db.scalar(select(Task).where(Task.thread_id == f"agent-build:{build.id}:root"))
        if not task:
            return
        task.current_action = action
        task.progress = min(100, progress)
        if completed:
            task.status, task.finished_at, task.result_summary = "completed", datetime.now(timezone.utc), action
        elif failed:
            task.status, task.finished_at, task.result_summary = "failed", datetime.now(timezone.utc), action
        elif cancelled:
            task.status, task.finished_at, task.result_summary = "cancelled", datetime.now(timezone.utc), action

    @staticmethod
    def _restore_project_after_failure(db: Session, build: AgentBuild) -> None:
        project = db.get(Project, build.project_id)
        if not project:
            return
        previous = (project.extra_config or {}).get("agentBuildPreviousStatus")
        mode = (build.plan or {}).get("_meta", {}).get("mode", "initial")
        project.status = previous if mode == "incremental" and previous else "failed"
        project.extra_config = {**(project.extra_config or {}), "activeAgentBuildId": None}
        project.updated_at = datetime.now(timezone.utc)
        if build.iteration_id:
            iteration = db.get(Iteration, build.iteration_id)
            if iteration:
                iteration.status = "failed"
                iteration.deploy_status = build.error_message or "Agent 构建失败"
                iteration.finished_at = datetime.now(timezone.utc)

    def _check_cancel(self, db: Session, build: AgentBuild) -> None:
        db.refresh(build)
        if build.cancellation_requested:
            raise BuildCancelled()

    def _log(self, db: Session, build: AgentBuild, stage: str, level: str, agent_key: str | None, message: str, metadata: dict[str, Any] | None = None) -> None:
        db.add(AgentBuildLog(build_id=build.id, stage=stage, level=level, agent_key=agent_key, message=message, metadata_json=metadata or {}))
        db.flush()

    @staticmethod
    def _add_usage(build: AgentBuild, result: LLMResult) -> None:
        build.prompt_tokens += result.prompt_tokens
        build.completion_tokens += result.completion_tokens

    @staticmethod
    def _test_result(name: str, result: ExecutionResult, attempt: int) -> dict[str, Any]:
        return {"name": name, "command": result.command, "passed": result.status == "completed" and result.exit_code == 0, "status": result.status, "exitCode": result.exit_code, "stdout": result.stdout[-15000:], "stderr": result.stderr[-15000:], "elapsedMs": result.elapsed_ms, "attempt": attempt}

    @staticmethod
    def _error_message(exc: Exception) -> str:
        if isinstance(exc, AppError):
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return str(detail.get("message", exc))
        return str(exc) or exc.__class__.__name__


def recover_stale_builds(db: Session) -> int:
    """Mark in-process builds interrupted by an API restart as retryable failures."""
    stale = db.scalars(select(AgentBuild).where(AgentBuild.status.in_(["pending", "running"]))).all()
    now = datetime.now(timezone.utc)
    for build in stale:
        build.status = "failed"
        build.current_stage = "failed"
        build.finished_at = now
        build.error_message = "API 服务重启导致构建中断，请点击重新构建。"
        db.add(AgentBuildLog(build_id=build.id, stage="failed", level="error", message=build.error_message, metadata_json={"recoverable": True}))
        root = db.scalar(select(Task).where(Task.thread_id == f"agent-build:{build.id}:root"))
        if root:
            root.status = "failed"
            root.finished_at = now
            root.result_summary = build.error_message
        project = db.get(Project, build.project_id)
        if project:
            previous = (project.extra_config or {}).get("agentBuildPreviousStatus")
            mode = (build.plan or {}).get("_meta", {}).get("mode", "initial")
            project.status = previous if mode == "incremental" and previous else "failed"
            project.extra_config = {**(project.extra_config or {}), "activeAgentBuildId": None}
    if stale:
        db.commit()
    return len(stale)


agent_build_runner = AgentBuildRunner()
