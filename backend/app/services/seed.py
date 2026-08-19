from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentMemory, AgentType, Artifact, Iteration, PipelineNode, PipelineTemplate, Project, ProjectMember, RequirementVersion, Task, TaskLog, User, VersionSnapshot
from app.core.auth import hash_password

NOW = datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc)


def seed_identity_data(db: Session) -> None:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        return
    users = [
        User(id="user-admin", email="admin@company.com", display_name="周明远", password_hash=hash_password("Admin@2026"), platform_role="super_admin", department="信息技术部"),
        User(id="user-linjia", email="lin.jia@company.com", display_name="林嘉", password_hash=hash_password("Agent@2026"), platform_role="user", department="人力资源部"),
        User(id="user-zhaowei", email="zhao.wei@company.com", display_name="赵玮", password_hash=hash_password("Agent@2026"), platform_role="platform_admin", department="信息技术部"),
        User(id="user-chenyu", email="chen.yu@company.com", display_name="陈屿", password_hash=hash_password("Agent@2026"), platform_role="user", department="人力资源部"),
        User(id="user-yanghan", email="yang.han@company.com", display_name="杨涵", password_hash=hash_password("Agent@2026"), platform_role="user", department="审计与风控部"),
    ]
    db.add_all(users)
    db.commit()


def seed_agent_configuration(db: Session) -> None:
    if (db.scalar(select(func.count(AgentType.id))) or 0) > 0:
        return
    definitions = [
        ("project-manager", "项目经理", "需求理解、任务规划和团队协调", "PM", ["requirement-analysis", "regression-plan"]),
        ("architect", "架构设计师", "系统架构、数据模型和增量方案", "AR", []),
        ("backend-developer", "后端开发工程师", "FastAPI、数据库和自动化测试", "BE", ["code-metrics"]),
        ("frontend-developer", "前端开发工程师", "Vue 3 页面、组件和交互", "FE", ["code-metrics"]),
        ("code-reviewer", "代码审查工程师", "安全、兼容性和代码质量", "CR", ["code-metrics", "regression-plan"]),
        ("test-engineer", "测试工程师", "单元、集成和回归测试", "QA", ["regression-plan"]),
        ("deployment-engineer", "部署工程师", "镜像、容器、健康检查和回滚", "DO", []),
    ]
    agents = {}
    for name, display, description, short, skills in definitions:
        item = AgentType(name=name, display_name=display, description=description, system_prompt=f"你是{display}。遵循最小化改动、测试优先和可追溯原则。", model="deepseek-chat", tools=["read_file", "write_file", "shell"], skills=skills, sandbox_config={"cpu": 2, "memoryMb": 512}, is_template=True)
        db.add(item); db.flush(); agents[name] = item
    templates = [
        ("web-fullstack", "Web 全栈应用", "fullstack", ["project-manager", "architect", "backend-developer", "frontend-developer", "code-reviewer", "test-engineer", "deployment-engineer"]),
        ("api-service", "API 后端服务", "api", ["project-manager", "architect", "backend-developer", "code-reviewer", "test-engineer", "deployment-engineer"]),
        ("frontend-app", "前端应用", "frontend", ["project-manager", "frontend-developer", "code-reviewer", "test-engineer", "deployment-engineer"]),
    ]
    for name, display, kind, sequence in templates:
        template = PipelineTemplate(name=name, display_name=display, description=f"系统预置{display}流程", template_type=kind, is_active=True, is_system=True, created_by="user-admin")
        db.add(template); db.flush()
        previous = None
        for position, agent_name in enumerate(sequence):
            node_key = f"{position+1}-{agent_name}"
            db.add(PipelineNode(template_id=template.id, node_key=node_key, agent_type_id=agents[agent_name].id, display_name=agents[agent_name].display_name, depends_on=[previous] if previous else [], execution_mode="sequential", position=position))
            previous = node_key
    db.commit()


def seed_demo_data(db: Session) -> None:
    seed_identity_data(db)
    if (db.scalar(select(func.count(Project.id))) or 0) > 0:
        return
    projects = [
        Project(id="leave-hub", name="员工假勤管理平台", description="覆盖请假申请、多级审批、额度管理与数据分析的一体化内部应用。", status="executing", progress=72, version="v1.3.0", template="Web 全栈应用", owner_name="林嘉", members=["LJ","ZW","CY","YH"], tasks_done=18, tasks_total=25, risk="low", created_at=NOW-timedelta(days=20), updated_at=NOW-timedelta(minutes=10)),
        Project(id="supplier-risk", name="供应商风险评估系统", description="汇聚供应商履约、财务与舆情数据，生成分级风险画像和预警。", status="testing", progress=86, version="v1.0.0-rc.2", template="Web 全栈应用", owner_id="user-zhaowei", owner_name="赵玮", members=["ZW","WL","YH"], tasks_done=31, tasks_total=36, risk="medium", created_at=NOW-timedelta(days=13), updated_at=NOW-timedelta(hours=1)),
        Project(id="contract-api", name="合同审查 API 服务", description="提供合同条款抽取、风险识别和审查意见生成的标准化 API。", status="completed", progress=100, version="v2.1.0", template="API 后端服务", owner_id="user-chenyu", owner_name="陈屿", members=["CY","ZW"], tasks_done=22, tasks_total=22, risk="low", created_at=NOW-timedelta(days=40), updated_at=NOW-timedelta(days=1)),
        Project(id="ops-board", name="运营数据驾驶舱", description="面向区域运营团队的核心指标监控、趋势分析与异常下钻看板。", status="draft", progress=12, version="—", template="前端应用", owner_name="林嘉", members=["LJ"], tasks_done=2, tasks_total=17, risk="low", created_at=NOW-timedelta(days=3), updated_at=NOW-timedelta(days=3)),
    ]
    db.add_all(projects)
    db.flush()
    db.add_all([
        ProjectMember(project_id="leave-hub", user_id="user-zhaowei", role="co_manager", invited_by="user-linjia"),
        ProjectMember(project_id="leave-hub", user_id="user-chenyu", role="member", invited_by="user-linjia"),
        ProjectMember(project_id="leave-hub", user_id="user-yanghan", role="viewer", invited_by="user-linjia"),
        ProjectMember(project_id="supplier-risk", user_id="user-linjia", role="member", invited_by="user-zhaowei"),
    ])

    iteration_rows = [
        ("i-130","v1.3.0",5,"新增报表 Excel 导出","支持按部门、日期和审批状态筛选后导出假勤明细，增加异步进度反馈。","executing",12,684,57,92,"等待回归测试","feature",NOW-timedelta(hours=2,minutes=24)),
        ("i-120","v1.2.0",4,"审批流程支持三级配置","审批节点由固定两级升级为可配置三级，兼容历史审批单据。","completed",18,1126,241,100,"运行中","feature",datetime(2026,8,12,8,42,tzinfo=timezone.utc)),
        ("i-111","v1.1.1",3,"修复跨月额度计算问题","修复跨月请假申请在额度扣减时的边界计算错误。","completed",4,73,31,100,"已归档","fix",datetime(2026,8,7,3,16,tzinfo=timezone.utc)),
        ("i-110","v1.1.0",2,"新增团队假勤日历","新增团队维度的月历视图，支持权限范围内的人员筛选。","completed",14,897,102,98,"已归档","feature",datetime(2026,8,1,10,5,tzinfo=timezone.utc)),
        ("i-100","v1.0.0",1,"首个生产版本","完成请假申请、两级审批、额度管理和基础数据报表。","completed",86,7642,0,96,"已归档","initial",datetime(2026,7,29,7,30,tzinfo=timezone.utc)),
    ]
    for row in iteration_rows:
        iid,version,seq,title,desc,status,files,added,removed,tests,deploy,kind,date=row
        db.add(Iteration(id=iid,project_id="leave-hub",version=version,sequence=seq,title=title,change_request=desc,description=desc,status=status,changed_files_count=files,lines_added=added,lines_removed=removed,test_pass_rate=tests,deploy_status=deploy,iteration_type=kind,started_at=date,finished_at=date+timedelta(hours=2) if status=="completed" else None,impact_analysis={"riskLevel":"low","modules":["后端","前端","测试"]}))
    db.flush()

    task_rows = [
        ("t-root",None,"项目规划与执行协调","项目经理智能体","PM","in_progress",72,10080,28400,0,"统筹本次增量迭代，持续评估任务依赖和项目风险。","持续评估任务依赖和项目风险"),
        ("t-req","t-root","需求解析与影响分析","需求分析智能体","RA","completed",100,720,8200,0,"结合当前代码、API 和历史需求，识别本次导出功能的影响范围。",""),
        ("t-arch","t-root","增量技术方案设计","架构设计智能体","AR","completed",100,1080,12700,2,"设计不破坏既有接口的导出任务与文件存储方案。",""),
        ("t-back","t-arch","开发报表导出接口","后端开发智能体","BE","completed",100,2880,24100,7,"实现按筛选条件导出 Excel 的异步任务接口及权限校验。",""),
        ("t-front","t-arch","新增导出交互组件","前端开发智能体","FE","completed",100,2160,18900,5,"在假勤报表页增加导出入口、进度反馈和下载状态。",""),
        ("t-review","t-root","增量代码审查","代码审查智能体","CR","completed",100,1260,13500,12,"检查兼容性、安全性、重复实现以及数据库访问性能。",""),
        ("t-test","t-root","回归测试与质量验证","测试工程师智能体","QA","in_progress",68,1860,16300,8,"执行 128 项既有回归用例和 24 项新增导出功能测试，验证已有功能不受影响。","执行 E2E：筛选假勤记录 → 发起导出 → 查询进度 → 下载文件"),
        ("t-deploy","t-root","构建镜像并灰度部署","部署智能体","DO","pending",0,0,0,0,"构建 v1.3.0 镜像，完成灰度部署与冒烟测试。",""),
    ]
    for index,row in enumerate(task_rows):
        tid,parent,name,agent,short,status,progress,duration,tokens,files,desc,action=row
        started=None if status=="pending" else NOW-timedelta(minutes=max(1,168-index*20))
        db.add(Task(id=tid,project_id="leave-hub",parent_task_id=parent,iteration_id="i-130",name=name,agent_type=agent,agent_short=short,status=status,progress=progress,duration_seconds=duration,token_used=tokens,files_count=files,description=desc,current_action=action,task_type="incremental",started_at=started,finished_at=started+timedelta(seconds=duration) if status=="completed" and started else None,thread_id=f"thread-{tid}"))
    db.flush()

    logs = [
        ("system","lifecycle","测试工程师智能体已启动，加载迭代 i-130 上下文。"),("info","message","读取变更影响分析：后端 7 个文件，前端 5 个文件，数据库 Schema 无变更。"),("tool","tool_call","tool.read_file → tests/regression/test_leave_approval.py"),("success","message","已识别 128 项既有回归用例，准备增量生成针对性用例。"),("tool","tool_call","tool.write_file → tests/export/test_report_export.py (+186 lines)"),("thinking","message","正在覆盖权限边界、空数据集、超大数据量和多语言文件名场景…"),("tool","tool_call","tool.shell → pytest tests/regression tests/export -q --maxfail=1"),("success","message","第一批 104/104 项测试通过，用时 13m 14s。"),("info","message","正在执行 E2E：用户筛选假勤记录 → 发起导出 → 查询进度 → 下载文件。"),("warning","message","发现文件名时区断言不稳定，已隔离并重新执行该用例。"),("success","message","重试通过。当前进度 68%，已通过 104 / 152。")]
    for idx,(level,event,msg) in enumerate(logs):
        db.add(TaskLog(task_id="t-test",level=level,event_type=event,message=msg,created_at=NOW-timedelta(minutes=33-idx*3)))

    base_files={"backend/app/services/approval.py":{"lines":120},"backend/app/api/approval.py":{"lines":85},"frontend/src/views/Approval.vue":{"lines":220},"tests/test_approval.py":{"lines":180}}
    manifests={
        "v1.0.0":{"files":base_files,"features":["请假申请","两级审批","额度管理","基础报表"],"schema":{"leave_request":"v1","approval_policy":"v1"}},
        "v1.1.0":{"files":{**base_files,"frontend/src/views/TeamCalendar.vue":{"lines":260,"churn":22},"backend/app/api/calendar.py":{"lines":98}},"features":["请假申请","两级审批","额度管理","基础报表","团队假勤日历"],"schema":{"leave_request":"v1","approval_policy":"v1"}},
        "v1.1.1":{"files":{**base_files,"backend/app/services/quota.py":{"lines":154,"churn":12,"removed":8}},"features":["请假申请","两级审批","额度管理","基础报表","团队假勤日历","跨月额度修复"],"schema":{"leave_request":"v1","approval_policy":"v1"}},
        "v1.2.0":{"files":{**base_files,"backend/app/services/approval.py":{"lines":173,"churn":31,"removed":31},"backend/app/api/approval.py":{"lines":115,"churn":12,"removed":12},"backend/app/models/workflow.py":{"lines":96,"removed":8},"frontend/src/views/ApprovalConfig.vue":{"lines":310,"churn":46,"removed":46},"frontend/src/components/StepEditor.vue":{"lines":218},"tests/test_three_level.py":{"lines":164}},"features":["请假申请","可配置三级审批","额度管理","基础报表","团队假勤日历","跨月额度修复"],"schema":{"leave_request":"v1","approval_policy":"v2-json-levels"}},
    }
    api_versions={
        "v1.0.0":{"endpoints":{"POST /leave":{"signature":"v1"},"POST /approval":{"signature":"v1"}}},
        "v1.1.0":{"endpoints":{"POST /leave":{"signature":"v1"},"POST /approval":{"signature":"v1"},"GET /calendar":{"signature":"v1"}}},
        "v1.1.1":{"endpoints":{"POST /leave":{"signature":"v1"},"POST /approval":{"signature":"v1"},"GET /calendar":{"signature":"v1"}}},
        "v1.2.0":{"endpoints":{"POST /leave":{"signature":"v1"},"POST /approval":{"signature":"v1"},"GET /calendar":{"signature":"v1"},"GET /approval/policies":{"signature":"v1"},"PUT /approval/policies/{id}":{"signature":"v1"}}},
    }
    for index,version in enumerate(["v1.0.0","v1.1.0","v1.1.1","v1.2.0"]):
        db.add(VersionSnapshot(project_id="leave-hub",iteration_id={"v1.0.0":"i-100","v1.1.0":"i-110","v1.1.1":"i-111","v1.2.0":"i-120"}[version],version=version,code_snapshot_path=f"snapshots/leave-hub/{version}.zip",code_manifest=manifests[version],db_schema_snapshot=f"-- schema {version}",api_snapshot=api_versions[version],docker_image_tag=f"registry.local/leave-hub:{version.lstrip('v')}",deploy_config_snapshot={"port":8080,"replicas":1},is_current=version=="v1.2.0",created_at=NOW-timedelta(days=19-index*5)))
    artifacts=[("代码仓库 v1.2.0","code","snapshots/leave-hub/v1.2.0.zip",8_400_000),("回归测试报告","test_report","reports/regression-v1.2.0.html",420_000),("架构设计文档","document","docs/architecture.md",86_000),("Docker 镜像 v1.2.0","image","registry.local/leave-hub:1.2.0",468_000_000)]
    for name,kind,path,size in artifacts: db.add(Artifact(project_id="leave-hub",iteration_id="i-120",name=name,artifact_type=kind,path=path,size_bytes=size,metadata_json={"version":"v1.2.0","status":"ready"}))
    db.commit()
    seed_runtime_data(db)


def seed_runtime_data(db: Session) -> None:
    """Seed runtime data independently so existing demo databases can be upgraded."""
    seed_identity_data(db)
    seed_agent_configuration(db)
    if not db.get(Project, "leave-hub"):
        return
    if (db.scalar(select(func.count(RequirementVersion.id)).where(RequirementVersion.project_id == "leave-hub")) or 0) == 0:
        project = db.get(Project, "leave-hub")
        db.add(RequirementVersion(project_id="leave-hub", version=1, title="员工假勤管理平台需求说明书", content_markdown=f"# 员工假勤管理平台\n\n{project.description}\n", structured_data={"summary": project.description}, status="confirmed", change_summary="演示项目初始需求", created_by="user-linjia"))
        db.commit()
    if (db.scalar(select(func.count(ProjectMember.id)).where(ProjectMember.project_id == "leave-hub")) or 0) == 0:
        db.add_all([
            ProjectMember(project_id="leave-hub", user_id="user-zhaowei", role="co_manager", invited_by="user-linjia"),
            ProjectMember(project_id="leave-hub", user_id="user-chenyu", role="member", invited_by="user-linjia"),
            ProjectMember(project_id="leave-hub", user_id="user-yanghan", role="viewer", invited_by="user-linjia"),
        ])
        db.commit()
    if (db.scalar(select(func.count(AgentMemory.id)).where(AgentMemory.project_id == "leave-hub")) or 0) > 0:
        return
    rows = [
        ("project-manager", "semantic", "business-goal", "员工应在 3 分钟内完成请假申请；审批人集中处理待办；HR 实时查看假勤趋势。", 0.95, ["requirement", "goal"]),
        ("project-manager", "semantic", "export-limit", "Excel 报表单次最多导出 50,000 条，超出时提示缩小筛选范围。", 0.9, ["export", "constraint"]),
        ("backend-developer", "procedural", "api-compatibility", "增量开发优先新增接口，不修改既有 API 签名；数据库采用向前兼容迁移。", 0.92, ["architecture", "compatibility"]),
        ("test-engineer", "episodic", "timezone-regression", "v1.3.0 回归测试曾发现导出文件名时区断言不稳定，重试后通过；后续需固定时区。", 0.82, ["testing", "regression"]),
        ("code-reviewer", "semantic", "security-rule", "所有数据导出接口必须复用项目权限规则并记录审计日志。", 0.88, ["security", "export"]),
    ]
    for agent, kind, key, content, importance, tags in rows:
        db.add(AgentMemory(project_id="leave-hub", agent_key=agent, scope="project" if agent == "project-manager" else "agent", memory_type=kind, key=key, content=content, importance=importance, tags=tags, metadata_json={"seed": True}))
    db.commit()
