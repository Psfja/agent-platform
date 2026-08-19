# 智构（Agent Studio）· 企业智能体平台

> 输入业务需求，由多智能体协作完成分析、设计、编码、测试、部署与持续迭代。

本项目依据《企业智能体平台 PRD V1.2》实现，当前已形成可运行的全栈 MVP：支持项目管理、DeepAgents 原生 SubAgent 编排、Agent 记忆与 Skills、真实 Vue + FastAPI 代码生成、自动测试与修复、增量迭代、Docker 部署、认证与 RBAC、Redis Worker、PostgreSQL/Alembic、需求与文档持久化，以及 Git、MinIO、通知和监控适配。

没有外部模型、Redis、MinIO 或 Docker 时，平台仍可启动并展示管理功能；真实 Agent 构建会明确提示缺少模型配置，不会使用 Mock 结果冒充成功。

---

## 目录

- [当前能力](#当前能力)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [产品页面](#产品页面)
- [核心执行流程](#核心执行流程)
- [主要 API](#主要-api)
- [测试与验证](#测试与验证)
- [演示账号](#演示账号)
- [当前边界](#当前边界)

---

## 当前能力

### 项目与需求

- 项目创建、搜索、暂停、继续、归档、恢复和软删除
- 项目所有者、协管员、成员、只读用户
- Markdown 需求版本、结构化需求、Draft/Confirmed 状态
- 需求澄清问题、回答和状态追踪
- PDF、Markdown、TXT、JSON、CSV、YAML 附件上传
- 附件 SHA-256、MinIO/本地存储和可读文本提取
- 架构、API、数据库、测试和部署文档版本化持久化

### DeepAgents 原生运行时

- `create_deep_agent` Supervisor
- 数据库驱动的声明式 SubAgents
- 原生 `task` Tool 委派
- FilesystemBackend
- TodoList、Skills 和 Memory
- OpenAI 兼容模型：DeepSeek、Qwen、One API、LiteLLM 等
- LangGraph SqliteSaver 持久 Checkpointer
- 平台级 AgentCheckpoint 阶段快照
- 阶段恢复和跳过已完成工作
- `request_database_migration` 原生 HITL
- `request_production_deployment` 原生 HITL
- Approve、Edit、Reject 后通过 `Command(resume=...)` 恢复

### Agent 记忆与 Skills

- Semantic、Episodic、Procedural、Working Memory
- 按项目、Agent、查询相关性和重要度召回
- Skill Manifest、输入 Schema 和 SHA-256 校验
- Skill 热重载
- Skill 代码只在沙箱执行，不导入 API 进程
- 内置需求分析、代码度量、回归测试计划 Skills

### 真实代码生成与质量门禁

- Vue 3 + Vite 前端生成
- FastAPI + Pydantic 后端生成
- 初始构建和基于成功版本的增量修改
- 受影响文件识别和文件 Manifest Diff
- 生成路径、文件大小、依赖与 npm scripts 白名单
- `pytest-cov` 覆盖率门禁，最低 80%
- Vitest 组件测试
- Vite Production Build
- Alembic Migration Gate
- 测试失败后自动诊断和修复，最多 5 轮
- 运行中人工追加指令
- 源码 ZIP、Git Commit 和 Artifact 记录

### 真实部署

- FastAPI Python 镜像
- Vue + Nginx 前端镜像
- 独立 Docker Network
- CPU、内存、PID、Capability 限制
- 后端仅在隔离网络可见
- Nginx 代理 `/api` 和 `/health`
- Docker 动态端口与访问 URL
- 首页和健康检查冒烟测试
- 新版本验证通过后停止旧容器
- 历史镜像保留、停止和回滚
- 前后端容器日志

### 认证与权限

- PBKDF2-SHA256 密码哈希
- JWT Access Token
- Refresh Token 持久化、轮换和撤销
- 通用 OIDC Discovery、JWKS 和授权码回调
- LDAP 搜索和密码绑定
- SSO 用户自动预配
- 超级管理员、平台管理员、普通用户
- Owner、Co-manager、Member、Viewer 项目 RBAC
- 项目列表和项目 API 数据隔离
- 登录、成员及关键操作审计

### 持久任务队列

- Redis 7 队列
- 数据库 `QueuedJob`
- 独立 Worker
- Worker ID 和心跳
- 失败重试、最大尝试次数和孤儿任务恢复
- Agent Build 与 Application Deployment Job
- Redis 不可用时开发线程降级

### 数据库与迁移

平台 Alembic Revision：

```text
0001_platform_baseline
0002_enterprise_runtime
0003_content_integrations
```

支持：

- 启动自动 `alembic upgrade head`
- SQLite Online Backup
- PostgreSQL `pg_dump`
- 备份 SHA-256
- 降级前强制备份
- `confirmation=DOWNGRADE` 二次确认
- 生成应用独立 PostgreSQL Schema
- 生成应用部署前备份
- Alembic Upgrade 失败自动恢复
- 回滚部署关联 `pg_restore`
- 镜像、Schema、Build 和 Deployment 版本关联

### 平台配置与外部集成

- AgentType CRUD、Prompt、Model、Tools、Skills、Sandbox
- AgentType 配置版本历史和使用中删除保护
- PipelineTemplate 与 PipelineNode CRUD
- 节点依赖、顺序/并行模式和引用校验
- 系统预置三套流程和需求关键词推荐
- Git Init、Branch、Commit 和可配置 Push
- MinIO 上传与本地文件降级
- 站内通知、SMTP 和 Webhook
- psutil 主机监控
- Prometheus `/metrics`
- 项目、任务、Agent Build、Deployment、Queue、Token 指标

---

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite 7
- Vue Router
- Pinia
- Lucide Icons
- 自定义企业级设计系统

### 后端

- Python 3.11+
- FastAPI
- SQLAlchemy 2
- Pydantic 2
- Alembic
- PostgreSQL / SQLite
- Redis 7
- MinIO
- DeepAgents
- LangGraph
- LangChain OpenAI-compatible client
- Docker / Nginx
- Prometheus Client / psutil

### 测试

- Pytest
- pytest-cov
- FastAPI TestClient
- Vitest
- Vue Test Utils
- Vite Production Build

---

## 系统架构

```text
┌──────────────────────────────────────────────────────────────┐
│                  Vue 3 + TypeScript SPA                      │
│ 项目 / 需求 / 任务 / 构建 / 迭代 / 部署 / Agent / 管理后台  │
└─────────────────────────────┬────────────────────────────────┘
                              │ REST + SSE + JWT
┌─────────────────────────────▼────────────────────────────────┐
│                           FastAPI                            │
│ Auth / Projects / Content / Agents / Builds / Deployments   │
└──────────────┬──────────────────┬──────────────────┬─────────┘
               │                  │                  │
┌──────────────▼───────┐ ┌────────▼─────────┐ ┌──────▼──────────┐
│ DeepAgents/LangGraph │ │ Redis Job Queue  │ │ Integrations    │
│ Supervisor/Subagents│ │ Durable Worker   │ │ Git/MinIO/SMTP  │
│ HITL/Checkpoint     │ │ Heartbeat/Retry  │ │ Webhook/Metrics │
└──────────────┬───────┘ └────────┬─────────┘ └──────┬──────────┘
               │                  │                  │
┌──────────────▼──────────────────▼──────────────────▼──────────┐
│ SQLAlchemy + PostgreSQL/SQLite + Alembic + Object Storage    │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│ Sandbox / Generated Workspace / Docker Build & Deployment   │
└──────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```text
agent-platform/
├── src/
│   ├── api/client.ts
│   ├── components/
│   ├── data/
│   ├── pages/
│   │   ├── AgentBuildPage.vue
│   │   ├── AgentRuntimePage.vue
│   │   └── admin/
│   │       ├── AgentTypesPage.vue
│   │       ├── AgentTypeEditPage.vue
│   │       ├── SkillsPage.vue
│   │       ├── PipelineTemplatesPage.vue
│   │       ├── ResourcesPage.vue
│   │       └── SettingsPage.vue
│   ├── stores/
│   ├── router.ts
│   ├── styles.css
│   └── additional.css
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── content.py
│   │   │   ├── tasks.py
│   │   │   ├── iterations.py
│   │   │   ├── agent_builds.py
│   │   │   ├── agent_config.py
│   │   │   ├── application_deployments.py
│   │   │   ├── operations.py
│   │   │   └── queue.py
│   │   ├── core/
│   │   ├── migrations/
│   │   │   └── versions/
│   │   ├── services/
│   │   │   ├── deepagents_runtime.py
│   │   │   ├── agent_builder.py
│   │   │   ├── application_deployer.py
│   │   │   ├── generated_database.py
│   │   │   ├── task_queue.py
│   │   │   ├── integrations.py
│   │   │   ├── sso.py
│   │   │   └── monitoring.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── main.py
│   │   └── worker.py
│   ├── skills/
│   ├── docker/
│   ├── tests/
│   ├── alembic.ini
│   ├── docker-compose.infrastructure.yml
│   ├── requirements.txt
│   └── .env.example
├── package.json
├── vite.config.ts
└── README.md
```

---

## 快速开始

### 环境要求

- Node.js 20.19+
- npm 10+
- Python 3.11+
- Docker 与 Docker Compose，可选但推荐

### 1. 安装前端依赖

```bash
npm install
```

### 2. 安装后端依赖

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

### 3. 启动基础设施

```bash
cd backend
docker compose -f docker-compose.infrastructure.yml up -d
```

包括 PostgreSQL、Redis 和 MinIO。若不启动，开发环境默认使用 SQLite、本地文件和线程队列降级。

### 4. 启动 API

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 启动 Redis Worker

Redis 可用时单独启动：

```bash
cd backend
.venv/bin/python -m app.worker
```

### 6. 启动前端

```bash
npm run dev -- --host 0.0.0.0
```

访问：

- 前端：`http://localhost:4173`
- Swagger：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`
- 健康检查：`http://localhost:8000/health`
- Prometheus：`http://localhost:8000/metrics`

---

## 环境配置

完整配置见 [`backend/.env.example`](backend/.env.example)。

### 平台与数据库

```env
APP_ENV=development
DATABASE_URL=sqlite:///./data/agent_platform.db
RUN_DB_MIGRATIONS=true
JWT_SECRET=replace-with-at-least-32-random-characters
```

PostgreSQL：

```env
DATABASE_URL=postgresql+psycopg://agent_platform:password@localhost:5432/agent_platform
```

### 模型与 DeepAgents

```env
LLM_BASE_URL=https://your-openai-compatible-gateway/v1
LLM_API_KEY=your-secret-key
LLM_MODEL=your-model-name
AGENT_ENGINE=deepagents
LANGGRAPH_CHECKPOINT_DB=data/langgraph_checkpoints.sqlite
SKILL_DIRECTORIES=./skills
```

未配置 `LLM_API_KEY` 时，真实 Agent Build 返回明确的 `503 LLM_NOT_CONFIGURED`。

### Redis Worker

```env
REDIS_URL=redis://localhost:6379/0
QUEUE_NAME=agent-platform
QUEUE_FALLBACK_THREADS=true
```

生产环境建议设置 `QUEUE_FALLBACK_THREADS=false` 并独立运行 Worker。

### 沙箱与部署

```env
SANDBOX_BACKEND=docker
SANDBOX_DOCKER_IMAGE=python:3.11-alpine
AGENT_BUILD_DOCKER_IMAGE=agent-build:py311-node20
DEPLOYMENT_PUBLIC_HOST=localhost
```

构建组合镜像：

```bash
cd backend
docker build -f docker/agent-build.Dockerfile -t agent-build:py311-node20 .
```

### 生成应用 PostgreSQL

```env
GENERATED_DATABASE_URL=postgresql://user:password@localhost:5432/generated_apps
GENERATED_DATABASE_BACKUP_DIR=data/generated-db-backups
```

启用后，每个生成项目使用独立 Schema；部署前执行 `pg_dump`，迁移失败或回滚时执行恢复。

### SSO

OIDC：

```env
OIDC_ISSUER=https://id.company.com
OIDC_CLIENT_ID=agent-platform
OIDC_CLIENT_SECRET=secret
OIDC_REDIRECT_URI=http://localhost:4173/login/callback
```

LDAP：

```env
LDAP_URL=ldaps://ldap.company.com
LDAP_BASE_DN=dc=company,dc=com
LDAP_BIND_DN=cn=agent-platform,ou=services,dc=company,dc=com
LDAP_BIND_PASSWORD=secret
```

### Git、MinIO 与通知

```env
GIT_REMOTE_URL=
GIT_DEFAULT_BRANCH=main

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=agent-platform
MINIO_SECURE=false

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
NOTIFICATION_WEBHOOK_URL=
```

生产密钥不得提交到仓库，应使用 Secret Manager 或部署平台密钥注入。

---

## 产品页面

| 页面 | 路径 |
|---|---|
| 登录与 SSO | `/login` |
| 项目空间 | `/projects` |
| 项目仪表盘 | `/projects/:id` |
| 需求说明书 | `/projects/:id/requirements` |
| 任务树 | `/projects/:id/tasks` |
| 任务详情 | `/projects/:id/tasks/:taskId` |
| 迭代历史 | `/projects/:id/iterations` |
| 迭代详情 | `/projects/:id/iterations/:iterId` |
| 版本对比 | `/projects/:id/compare` |
| 代码仓库 | `/projects/:id/code` |
| 项目文档 | `/projects/:id/docs` |
| AI 全栈构建 | `/projects/:id/build` |
| 部署中心 | `/projects/:id/deployments` |
| Agent 运行时 | `/projects/:id/runtime` |
| 成员与协作 | `/projects/:id/members` |
| 产物中心 | `/projects/:id/artifacts` |
| 创建智能体 | `/admin/agent-types/new` |
| 智能体类型 | `/admin/agent-types` |
| Skill 管理与装配 | `/admin/skills` |
| 流程模板 | `/admin/pipeline-templates` |
| 用户与权限 | `/admin/users` |
| 资源监控 | `/admin/resources` |
| 系统设置 | `/admin/settings` |

### 左侧导航结构

登录后左侧导航按以下分组展示；菜单始终可见，实际读写能力由后端 JWT/RBAC 决定：

```text
工作空间
└── 项目空间

智能体工坊
├── 创建智能体
├── 智能体管理
├── Skill 管理与装配
└── 开发流程编排

接入与平台
├── 模型与 API 配置
├── 资源与运行监控
└── 用户与权限
```

对应路径：

| 导航项 | 路径 | 说明 |
|---|---|---|
| 项目空间 | `/projects` | 项目创建、搜索和状态管理 |
| 创建智能体 | `/admin/agent-types/new` | 创建 AgentType，配置 Prompt、模型、Tools、Skills 和沙箱 |
| 智能体管理 | `/admin/agent-types` | AgentType 列表、执行数据和配置版本 |
| Skill 管理与装配 | `/admin/skills` | Skill 扫描、校验、沙箱试运行及 Agent 装配 |
| 开发流程编排 | `/admin/pipeline-templates` | PipelineTemplate 与节点依赖管理 |
| 模型与 API 配置 | `/admin/settings` | 模型网关、Git、通知、安全和通用设置 |
| 资源与运行监控 | `/admin/resources` | 资源、Token、Worker 和 Agent 实例监控 |
| 用户与权限 | `/admin/users` | 平台用户、角色和账号状态 |

`Skill 管理与装配` 页面读取后端真实 Skill Registry，可重新扫描 `SKILL_DIRECTORIES`、查看 Manifest/入口文件/SHA-256、执行沙箱测试，并跳转到：

```text
/admin/agent-types/{agentKey}?tab=capabilities
```

直接配置指定智能体的 Tools 与 Skills。

---

## 核心执行流程

### 新项目

```text
创建项目
→ 保存需求版本与附件
→ 需求澄清/确认
→ 推荐流程模板
→ DeepAgents Supervisor
→ SubAgents 规划、前后端开发、审查和测试
→ pytest-cov / Alembic / Vitest / Vite Build
→ 失败自动修复
→ Git Commit + ZIP + MinIO
→ Docker 双镜像
→ PostgreSQL 备份与迁移
→ HITL 生产部署审批
→ 容器启动与冒烟测试
→ 版本快照、文档和通知
```

### 增量迭代

```text
提交变更
→ 影响分析
→ 用户确认
→ 选择最近成功 Build
→ 克隆源码
→ DeepAgents 增量修改
→ 完整回归门禁
→ 文件 Diff + VersionSnapshot
→ PostgreSQL 备份/Alembic
→ 自动部署或 HITL
→ 更新时间线与项目文档
```

### HITL

```text
敏感 Tool Call
→ LangGraph Interrupt
→ Build = waiting_approval
→ 用户 Approve/Edit/Reject
→ Command(resume={decisions: [...]})
→ 从原生 Checkpoint 恢复
```

---

## 主要 API

### 认证

```text
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/auth/sso/status
GET  /api/v1/auth/sso/oidc/start
POST /api/v1/auth/sso/oidc/callback
POST /api/v1/auth/sso/ldap
```

### 项目内容

```text
GET/POST /api/v1/projects/{id}/requirements
GET/POST /api/v1/projects/{id}/documents
GET/POST /api/v1/projects/{id}/attachments
GET/POST /api/v1/projects/{id}/clarifications
POST     /api/v1/projects/{id}/clarifications/{clarificationId}/answer
```

### Agent 构建与 HITL

```text
GET  /api/v1/agent-build/status
POST /api/v1/projects/{id}/agent-builds
GET  /api/v1/projects/{id}/agent-builds/{buildId}
POST /api/v1/projects/{id}/agent-builds/{buildId}/instructions
POST /api/v1/projects/{id}/agent-builds/{buildId}/hitl
POST /api/v1/projects/{id}/agent-builds/{buildId}/cancel
POST /api/v1/projects/{id}/agent-builds/{buildId}/retry
GET  /api/v1/projects/{id}/agent-builds/{buildId}/download
```

### 部署和数据库

```text
GET  /api/v1/deployment-runtime/status
POST /api/v1/projects/{id}/application-deployments
POST /api/v1/projects/{id}/application-deployments/{deploymentId}/stop
POST /api/v1/projects/{id}/application-deployments/{deploymentId}/rollback
GET  /api/v1/projects/{id}/application-deployments/{deploymentId}/container-logs
POST /api/v1/queue/database/backups
GET  /api/v1/queue/database/backups
POST /api/v1/queue/database/downgrade
GET  /api/v1/queue/migrations
```

### 管理与监控

```text
GET/POST/PATCH/DELETE /api/v1/admin/agent-types
GET/POST/PUT          /api/v1/admin/pipeline-templates
GET                    /api/v1/queue/status
GET                    /api/v1/queue/jobs
GET                    /api/v1/monitoring/summary
GET                    /api/v1/integrations/status
GET                    /api/v1/notifications
GET                    /metrics
```

完整请求和响应模型请查看 Swagger UI。

---

## 测试与验证

```bash
npm run build
npm audit --audit-level=moderate

cd backend
.venv/bin/pytest
```

当前结果：

- 后端集成测试：`21 passed`
- TypeScript 检查：通过
- Vite Production Build：通过
- npm audit：`0 vulnerabilities`
- Alembic：`0003_content_integrations`，与 Head 一致

集成测试覆盖：

- JWT、Refresh Token、RBAC 和项目隔离
- AgentType 与 PipelineTemplate
- 记忆、Skills 和沙箱
- 初始/增量代码生成
- 覆盖率、Vitest、Vite 和自动修复
- 文件 Diff、ZIP 和 Git
- Docker Runtime 受控部署
- 迭代自动串联
- Redis 队列状态
- Alembic Revision
- 需求、文档、附件和澄清持久化
- 真实监控和外部集成状态

外部 DeepAgents 模型、企业 OIDC/LDAP、真实 PostgreSQL、MinIO、Git Remote 和 Docker daemon 需要由部署环境提供凭据和服务后进行最终联调。

---

## 演示账号

项目用户：

```text
lin.jia@company.com
Agent@2026
```

超级管理员：

```text
admin@company.com
Admin@2026
```

平台管理员：

```text
zhao.wei@company.com
Agent@2026
```

生产环境必须删除或修改演示密码，并配置独立 `JWT_SECRET`。

---

## 当前边界

已实现核心能力，但以下内容仍需部署环境或后续增强：

- 真实模型 Key 未配置时不能运行 DeepAgents Build
- 当前预览环境未提供 Redis、MinIO、PostgreSQL、Docker daemon 和 Git Remote
- 企业微信专用 OAuth 与钉钉专用消息格式尚未单独封装
- Docker 部署使用动态端口，尚未接入固定域名、HTTPS 和蓝绿流量代理
- 本地进程沙箱不提供可靠网络/文件系统边界，生产必须使用 Docker Sandbox
- DeepAgents 原生 Checkpointer 当前使用 SQLite；多节点生产可切换 PostgreSQL Checkpointer
- 生成应用 PostgreSQL 回滚依赖部署机器安装 `pg_dump` 和 `pg_restore`
- 前端部分资源图表仍保留演示数据，后端真实监控 API 已可用
- 仍需补充 Playwright E2E、SAST、镜像扫描、SBOM 和大规模并发验收

---

## License

当前项目用于产品原型和企业内部研发验证。正式开源或商业发布前，请补充许可证、第三方依赖合规和安全审计说明。
