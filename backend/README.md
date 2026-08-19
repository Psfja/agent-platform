# 智构企业智能体平台 API

对应 PRD 核心闭环的 FastAPI 后端实现。项目管理和规则型影响分析无需模型密钥即可运行；配置 OpenAI 兼容网关后，可启动真实分阶段 Agent，生成 Vue + FastAPI 源码并执行 pytest、Vite build 和失败自动修复。通过 `DATABASE_URL` 可切换 PostgreSQL。

## 已实现能力

- 项目创建、查询、修改、暂停/继续、归档和 30 天软删除语义
- 创建项目时自动初始化“项目经理智能体”任务
- 任务树、任务详情、状态操作、日志搜索
- 人工干预指令排队及“任务已结束”保护
- 增量需求影响分析：模块、文件、数据库/API 影响、风险、建议智能体
- 确认迭代后按影响范围创建最小智能体任务集合
- 迭代时间线、版本快照、代码/Schema/API/功能差异
- 双重确认的版本回滚流程
- 项目产物查询
- 项目级 SSE 实时事件流
- SQLite 演示数据与 PostgreSQL 配置兼容
- 持久化 Agent 记忆：semantic、episodic、procedural、working
- 按项目、Agent、任务查询和重要度召回记忆，并生成可注入 Prompt
- 动态 Skill 注册表：目录扫描、Manifest 校验、SHA-256 校验和热重载
- 内置三个可执行 Skills：需求分析、代码度量、回归测试计划
- Skill 代码仅在沙箱执行，不导入 API 进程
- 本地资源限制沙箱和 Docker 无网络沙箱双后端
- 任务编排时自动绑定 Skills、召回记忆并写入执行元数据
- OpenAI 兼容真实模型客户端，支持 DeepSeek、Qwen、One API 和 LiteLLM
- 架构、后端、前端、测试和修复 Agent 的真实分阶段执行
- Vue + FastAPI 文件生成、路径/大小/依赖/npm scripts 安全校验
- 支持基于上一成功工作区的增量克隆、最小化修改和文件 Diff
- 自动执行 pytest-cov（覆盖率 ≥80%）、npm install（禁用 scripts）、Vitest 和 Vite production build
- 运行中可提交人工指令，并在下一 Agent 安全阶段注入上下文
- 测试失败后基于源码和错误日志自动修复，成功后生成 ZIP 产物
- 为成功构建创建 FastAPI 与 Vue/Nginx 双镜像和隔离 Docker Network
- 动态端口、访问 URL、首页/健康检查冒烟测试和安全版本替换
- 真实部署停止、容器日志、历史构建回滚及失败清理
- PBKDF2 密码、JWT Access/Refresh 轮换、注销、平台角色和项目级 RBAC
- Redis 持久任务队列、数据库 Job、独立 Worker、心跳、重试和线程降级
- 迭代确认后自动选择基础 Build、增量生成、回归、快照和可用时自动部署
- Alembic Baseline、启动自动升级、在线备份、受确认降级和生成应用迁移门禁
- 通用 OIDC/JWKS 与 LDAP SSO 适配器
- SQLAlchemy LangGraph 风格 Checkpoint、阶段恢复和历史记录
- AgentType、PipelineTemplate/Node CRUD、配置版本和依赖校验
- Git Commit/Push、MinIO、本地存储、SMTP、Webhook 和站内通知
- psutil 资源指标、业务统计和 Prometheus `/metrics`
- 统一请求 ID、参数校验和业务错误结构

## 目录

```text
backend/
├── app/
│   ├── api/                 # 项目、任务、迭代、产物与事件路由
│   ├── core/                # 配置与业务错误
│   ├── services/            # 编排、记忆、Skill、沙箱、版本比较和事件总线
│   ├── database.py          # SQLAlchemy 会话与建表
│   ├── models.py            # 核心数据模型
│   ├── schemas.py           # Pydantic API Schema
│   ├── serializers.py       # ORM → API 转换
│   └── main.py              # FastAPI 应用入口
├── skills/                  # 文件系统 Skill 包（skill.json + SKILL.md + entrypoint）
├── tests/                   # API 集成测试
├── .env.example
├── requirements.txt
└── run.py
```

## 快速启动

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env       # 可选
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

演示账号：

- 项目用户：`lin.jia@company.com` / `Agent@2026`
- 超级管理员：`admin@company.com` / `Admin@2026`

访问：

- Swagger UI：`http://localhost:8000/docs`
- OpenAPI JSON：`http://localhost:8000/api/v1/openapi.json`
- 健康检查：`http://localhost:8000/health`

前端 Vite 已将 `/api` 和 `/health` 代理到 `127.0.0.1:8000`。

启动 PostgreSQL、Redis 和 MinIO：

```bash
docker compose -f docker-compose.infrastructure.yml up -d
```

Redis 可用时需启动独立 Worker：

```bash
.venv/bin/python -m app.worker
```

Redis 不可用且 `QUEUE_FALLBACK_THREADS=true` 时，开发环境会自动降级到进程内线程执行；Job 状态仍写入数据库。

## 运行测试

```bash
.venv/bin/pytest
```

当前覆盖 21 条集成测试：除项目核心闭环外，还验证 Skill、记忆、沙箱、模型 JSON、真实 Agent 初始/增量构建、人工指令、质量门禁，以及使用可控 Docker Runtime 完成双镜像部署、URL、冒烟测试和停止清理。

## 主要接口

| Method | Endpoint | 用途 |
|---|---|---|
| GET/POST | `/api/v1/projects` | 查询/创建项目 |
| GET/PATCH/DELETE | `/api/v1/projects/{id}` | 项目详情、更新、软删除 |
| POST | `/api/v1/projects/{id}/actions` | 暂停、继续、归档、恢复 |
| GET | `/api/v1/projects/{id}/dashboard` | 项目仪表盘聚合数据 |
| GET | `/api/v1/projects/{id}/tasks` | 任务树 |
| POST | `/api/v1/projects/{id}/tasks/{taskId}/actions` | 暂停、继续、终止、重试任务 |
| GET | `/api/v1/projects/{id}/tasks/{taskId}/logs` | 任务日志与搜索 |
| POST | `/api/v1/projects/{id}/tasks/{taskId}/interventions` | 提交人工干预 |
| POST | `/api/v1/projects/{id}/iterations/impact-analysis` | 生成变更影响分析 |
| POST | `/api/v1/projects/{id}/iterations/{iterId}/confirm` | 确认并启动增量迭代 |
| GET | `/api/v1/projects/{id}/iterations` | 迭代时间线 |
| GET | `/api/v1/projects/{id}/versions/compare` | 版本对比 |
| POST | `/api/v1/projects/{id}/versions/{version}/rollback` | 版本回滚 |
| GET | `/api/v1/projects/{id}/artifacts` | 产物列表 |
| GET | `/api/v1/projects/{id}/events` | SSE 实时事件流 |
| GET/POST | `/api/v1/projects/{id}/memories` | 查询/写入持久记忆 |
| GET | `/api/v1/projects/{id}/agents/{agentKey}/context` | 构建 Agent 运行时上下文 |
| GET/POST | `/api/v1/skills` / `/api/v1/skills/reload` | 查询或重载 Skills |
| POST | `/api/v1/projects/{id}/skills/{name}/execute` | 在沙箱执行 Skill |
| GET | `/api/v1/sandbox/status` | 查询沙箱能力 |
| POST | `/api/v1/projects/{id}/sandbox/runs` | 执行 Python 代码 |
| GET | `/api/v1/projects/{id}/sandbox/runs` | 查询沙箱历史 |
| GET | `/api/v1/agent-build/status` | 真实模型配置状态 |
| POST | `/api/v1/projects/{id}/agent-builds` | 启动 Vue + FastAPI 真实构建 |
| GET | `/api/v1/projects/{id}/agent-builds/{buildId}` | 构建阶段、日志和测试结果 |
| POST | `/api/v1/projects/{id}/agent-builds/{buildId}/cancel` | 取消构建 |
| POST | `/api/v1/projects/{id}/agent-builds/{buildId}/instructions` | 追加人工干预指令 |
| POST | `/api/v1/projects/{id}/agent-builds/{buildId}/retry` | 重试失败构建 |
| GET | `/api/v1/projects/{id}/agent-builds/{buildId}/download` | 下载生成源码 ZIP |
| GET | `/api/v1/deployment-runtime/status` | Docker 应用运行时状态 |
| POST | `/api/v1/projects/{id}/application-deployments` | 部署成功构建 |
| GET | `/api/v1/projects/{id}/application-deployments/{deploymentId}` | 部署阶段与冒烟结果 |
| POST | `/api/v1/projects/{id}/application-deployments/{deploymentId}/stop` | 停止真实容器 |
| POST | `/api/v1/projects/{id}/application-deployments/{deploymentId}/rollback` | 基于历史构建重新部署 |
| GET | `/api/v1/projects/{id}/application-deployments/{deploymentId}/container-logs` | 容器日志 |

## 真实 Agent 构建

在 `.env` 配置：

```env
LLM_BASE_URL=https://your-openai-compatible-gateway/v1
LLM_API_KEY=your-secret-key
LLM_MODEL=your-model-name
```

执行阶段：

1. 架构 Agent 根据需求、记忆与 Skills 输出结构化方案；
2. 后端 Agent 生成 FastAPI、Pydantic 与 pytest；
3. 前端 Agent 生成 Vue 3、Vite 与自包含样式；
4. 测试 Agent 执行 pytest-cov、依赖安装、Vitest 和 production build；
5. 失败时将日志和当前源码交给修复 Agent；
6. 增量模式从成功构建克隆源码，仅应用模型返回的受影响文件；
7. 全部门禁通过后生成文件 Diff、ZIP、Artifact 和情景记忆。

模型不能任意写入宿主目录：所有路径必须位于生成工作区的 `backend/`、`frontend/` 或 `docs/`；前端依赖、Python 依赖及 npm build script 均经过白名单校验。API 服务重启时，未完成构建会标记为可重试失败，而不会长期停留在运行状态。

## 真实应用部署

成功构建可进入真实 Docker 部署：

1. 平台写入受控后端和前端 Dockerfile；
2. 构建 FastAPI Python 镜像及 Vue/Nginx 镜像；
3. 创建项目版本专属 Docker Network；
4. 后端仅在内部网络使用 `backend:8000`，不直接暴露主机；
5. 前端 Nginx 发布动态主机端口并代理 `/api`、`/health`；
6. 自动验证首页和健康检查；
7. 新版本通过后停止旧容器，保留历史镜像；
8. 失败时清理新容器与网络，不影响旧版本。

容器使用内存、CPU、PID、Capability 和 `no-new-privileges` 限制。`DEPLOYMENT_PUBLIC_HOST` 控制返回 URL 的主机名；生产环境下一步应接入 Nginx 固定域名和 HTTPS。

## Agent 记忆

`AgentMemory` 持久化以下四类记忆：

- `semantic`：项目事实与业务约束；
- `episodic`：历史执行结果与问题经验；
- `procedural`：Agent 操作规范和团队约定；
- `working`：可设置过期时间的临时工作记忆。

创建增量任务时，编排器会按项目、Agent 类型、当前需求和重要度召回记忆，将记忆 ID 与 Skill 名称写入 `Task.execution_metadata`，并生成 `runtime_context` 类型日志。

## Skill 格式

每个 Skill 放在独立目录：

```text
skills/my-skill/
├── skill.json   # 名称、版本、适用 Agent、输入 Schema 与入口
├── SKILL.md     # 注入 Agent 上下文的使用说明
└── main.py      # 可选执行入口，只在沙箱运行
```

修改 `SKILL_DIRECTORIES` 可增加企业私有 Skill 目录；调用 `/api/v1/skills/reload` 可在不重启服务的情况下重新扫描。

## 沙箱模式

默认配置：

```env
SANDBOX_BACKEND=local
SANDBOX_TIMEOUT_SECONDS=30
SANDBOX_MEMORY_MB=256
SANDBOX_CPU_SECONDS=20
```

- `local`：使用 Python 隔离模式、独立工作目录、CPU/内存/文件大小/进程数限制。适合开发联调，但**不提供可靠的文件系统边界和网络隔离**。
- `docker`：使用只读容器、`--network none`、`--cap-drop ALL`、`no-new-privileges`、内存/CPU/PID 限制。生产环境推荐。

启用 Docker：

```env
SANDBOX_BACKEND=docker
SANDBOX_DOCKER_IMAGE=python:3.11-alpine
AGENT_BUILD_DOCKER_IMAGE=agent-build:py311-node20
```

构建全栈镜像：

```bash
docker build -f docker/agent-build.Dockerfile -t agent-build:py311-node20 .
```

Docker 模式下，pytest 和 Vite build 使用 `--network none`；只有经过依赖白名单校验的 `npm install --ignore-scripts` 阶段允许容器访问依赖源。

## PostgreSQL 切换

在 `.env` 中设置：

```env
DATABASE_URL=postgresql+psycopg://agent_platform:password@localhost:5432/agent_platform
```

当前开发版启动时使用 SQLAlchemy `create_all` 创建表。正式部署时建议下一阶段接入 Alembic 版本化迁移，并将单进程 SSE 事件总线替换为 Redis Pub/Sub。

## Mock 边界

项目创建和增量影响分析仍保留规则型实现，原有演示任务也不会自动变成 LLM 任务；但 `/agent-builds` 流水线会真实调用 OpenAI 兼容模型、写入源码并执行测试。当前编排器是项目内实现的分阶段 Agent Runner，尚未采用 DeepAgents/LangGraph Middleware 与 Checkpointer。
