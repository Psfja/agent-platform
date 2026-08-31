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
- [改进路线](#改进路线)
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
- 内置需求分析、代码度量、回归测试计划、前端设计审计与优化 Skills
  （ui-redesign 基于 taste-skill 的 redesign 技能适配，MIT 协议署名）

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
- 通用 OIDC Discovery、JWKS 和授权码回调（前端 `/login/callback` 完整闭环）
- LDAP 搜索和密码绑定
- SSO 用户自动预配
- 超级管理员、平台管理员、普通用户
- 平台用户管理 API：列表、创建（自动生成初始密码）、角色变更、启停、密码重置和删除保护
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

- AgentType CRUD、Prompt、Model、Tools、Skills、Sandbox 与真实 Temperature（0–1，实际作用于对话/Agent 调用）
- AgentType 配置版本历史、引用统计（被哪些流程模板引用）与使用中删除保护（无引用可直接删除）
- PipelineTemplate 与 PipelineNode CRUD
- 节点依赖、顺序/并行模式和引用校验
- 系统预置三套流程和需求关键词推荐
- AI 流程生成：自然语言描述需求 → 模型网关生成流程草稿（引用真实 AgentType，自动清洗非法标识/无效引用/环依赖，无 Key 时明确报错不 Mock）
- 流程图编排：SVG 流程图可视化；拖拽节点调整位置；从节点右侧把手拖到另一节点左侧把手建立依赖；点击连线删除；节点增删与自动布局；依赖面板勾选编辑；画布坐标随模板持久化
- 平台用户管理：创建（一次性初始密码）、角色变更、启停、密码重置；删除时可将名下项目一键移交当前管理员
- 智能体对话：每个智能体均有独立会话（按项目），支持长期记忆、上下文管理与多轮对话
- 对话上下文：Agent 人设 + 按相关性召回的持久记忆 + 装配的 Skills 指令 + 历史消息（Token 预算自动裁剪旧消息）
- 对话长期记忆：每轮对话自动提取值得记住的事实写入 Episodic 记忆（可开关），下次对话自动召回
- 记忆语义召回：配置 embedding 模型后按 关键词×0.5 + 余弦相似度×0.5 混合重排，不可用时自动降级关键词排序
- SSE 流式回复：逐 Token 打字机输出（fetch + ReadableStream 解析），提供方不支持 stream 时自动降级
- AI 会话标题：首条回复后自动生成标题，可随时点击魔法按钮基于最近消息重新生成
- 对话工具模式（DeepAgents）：每个对话可切换为真实智能体——项目专属文件工作区（FilesystemBackend）、
  Python 沙箱工具、TodoList、平台子智能体委派（task tool）、Skills 与长期记忆注入、生产部署 HITL
  中断（流式事件触发审批卡片，批准/编辑/驳回后从检查点恢复继续执行）
- Git Init、Branch、Commit 和可配置 Push
- MinIO 上传与本地文件降级
- 站内通知、SMTP 和 Webhook
- psutil 主机监控
- Prometheus `/metrics`
- 项目、任务、Agent Build、Deployment、Queue、Token 指标
- 管理后台（智能体/流程/用户/设置/资源）全部接入真实 API
- 前端设计体系：按 ui-redesign 审计 18/18 通过——z-index 令牌、tabular-nums 数字排版、
  按压反馈与减动效、骨架屏、品牌 favicon、OG meta、100dvh 布局、死链清零

### 平台自身容器化部署

- FastAPI/Worker 单镜像（`backend/docker/platform-api.Dockerfile`，非 root 运行）
- Vue + Nginx 前端镜像（`docker/frontend.Dockerfile`，SPA 回退、`/api` `/health` 反向代理、SSE 关闭缓冲、前端探活 `/healthz`）
- `docker-compose.production.yml`：PostgreSQL + Redis + API + Worker + 前端一体化编排，含健康检查、重启策略、数据卷与可选 MinIO（`--profile storage`）
- 根目录 `.env.docker.example` 提供全部部署环境变量模板

### 持续集成

- `.github/workflows/ci.yml`：push 与 PR 自动执行
  - 后端：Python 3.11 + pytest + Alembic 单 head 校验
  - 前端：npm ci + Vitest 单元测试 + vue-tsc + Vite 生产构建 + npm audit

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
├── .github/workflows/ci.yml        # CI：后端 pytest + Alembic，前端 Vitest + 构建 + audit
├── docker/
│   ├── frontend.Dockerfile         # 平台前端镜像（Vue 构建 + Nginx）
│   └── nginx.conf                  # SPA 回退与 /api、/health 反向代理
├── docker-compose.production.yml   # 平台本体生产编排（PostgreSQL/Redis/API/Worker/前端/MinIO）
├── .env.docker.example             # Compose 环境变量模板
├── src/
│   ├── api/client.ts
│   ├── components/
│   ├── data/
│   ├── pages/
│   │   ├── AgentBuildPage.vue
│   │   ├── AgentRuntimePage.vue
│   │   ├── LoginCallbackPage.vue   # 企业 OIDC 授权码回调
│   │   └── admin/
│   │       ├── AgentTypesPage.vue
│   │       ├── AgentTypeEditPage.vue
│   │       ├── SkillsPage.vue
│   │       ├── PipelineTemplatesPage.vue
│   │       ├── ResourcesPage.vue
│   │       ├── SettingsPage.vue
│   │       └── UsersPage.vue
│   ├── stores/
│   ├── router.ts
│   ├── styles.css
│   ├── additional.css
│   └── **/*.test.ts                # 前端 Vitest 单元测试（38 个）
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── admin_users.py      # 平台用户管理
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
│   │   ├── platform-api.Dockerfile # 平台 API/Worker 镜像
│   │   └── agent-build.Dockerfile  # 生成应用构建镜像
│   ├── tests/
│   ├── alembic.ini
│   ├── docker-compose.infrastructure.yml
│   ├── requirements.txt
│   └── .env.example
├── package.json
├── vite.config.ts                  # 含 Vitest 配置
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

### 7. （可选）Docker 一键部署平台本体

```bash
cp .env.docker.example .env    # 修改 JWT_SECRET 等
docker compose -f docker-compose.production.yml up -d --build
# 可选对象存储：
docker compose -f docker-compose.production.yml --profile storage up -d
```

将构建平台 API/Worker 镜像与 Vue+Nginx 前端镜像，并启动 PostgreSQL、Redis。访问：

- 前端（经 Nginx）：`http://localhost:8080`
- Swagger：`http://localhost:8000/docs`

详见 `docker-compose.production.yml` 头部说明（`docker.sock` 挂载与沙箱配置注意事项）。

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

### 对话与上下文

```env
CONVERSATION_CONTEXT_TOKENS=6000
CONVERSATION_HISTORY_MIN_MESSAGES=12
EMBEDDING_MODEL=           # 留空则沿用 LLM_MODEL；不支持 embedding 的网关自动降级关键词召回
```

每轮对话召回长期记忆并裁剪超出 Token 预算的早期消息；未配置 `LLM_API_KEY` 时对话返回明确的 `503 LLM_NOT_CONFIGURED`。

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
POST                  /api/v1/admin/pipeline-templates/generate
POST                  /api/v1/admin/pipeline-templates/recommend
GET/POST/PATCH/DELETE /api/v1/admin/users
GET/POST               /api/v1/projects/{id}/conversations
GET/PATCH/DELETE       /api/v1/projects/{id}/conversations/{conversationId}
POST                   /api/v1/projects/{id}/conversations/{conversationId}/messages
POST                   /api/v1/projects/{id}/conversations/{conversationId}/messages/stream   # SSE
POST                   /api/v1/projects/{id}/conversations/{conversationId}/title
GET                    /api/v1/projects/{id}/conversations/{conversationId}/interrupts
POST                   /api/v1/projects/{id}/conversations/{conversationId}/interrupts/{interruptId}/decide
GET                    /api/v1/projects/{id}/conversations/{conversationId}/workspace
GET                    /api/v1/settings/status
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
npm run test                        # 前端单元测试（Vitest + Vue Test Utils）
npm run build                       # vue-tsc 类型检查 + Vite 生产构建
npm audit --audit-level=moderate

cd backend
.venv/bin/pytest                    # 后端集成测试
.venv/bin/python -m alembic heads   # 迁移单 head 校验
```

`.github/workflows/ci.yml`（pytest/Alembic + Vitest/构建/audit 流水线）已随仓库准备好；由于当前推送使用的 GitHub App 令牌缺少 workflows 权限，该文件尚未进入远程分支，请用具备权限的账号提交一次即可启用自动检查。

当前结果：

- 后端集成测试：`33 passed`
- 前端单元测试：`64 passed`（API 客户端、路由守卫、OIDC 回调、管理页、流程图、对话面板/工具模式/审批、删除与移交流程）
- 前端设计审计：`ui-redesign` Skill 18/18 项通过
- Playwright E2E：登录导航、项目工作区、流程编排 3 组用例（`scripts/e2e.sh`；登录/导航类用例无需模型 Key，需可下载 Chromium 的网络环境）
- 安全与验收脚手架：`scripts/security.sh`（Semgrep/Trivy/Syft）、`locustfile.py` 并发压测
- TypeScript 检查：通过
- Vite Production Build：通过
- npm audit：`0 vulnerabilities`
- Alembic：`0006_agent_type_temperature`，与 Head 一致

集成测试覆盖：

- 智能体对话：会话 CRUD、上下文组装（记忆+Skills+历史）、Token 预算裁剪、记忆自动提取与未配置模型 503
- JWT、Refresh Token、RBAC 和项目隔离
- 平台用户管理（创建/角色/启停/密码重置/删除保护）与系统设置状态脱敏
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

## 改进路线

按优先级排列的后续计划；标注「免 Key」的项不依赖模型/外部服务即可实施。

### P0 · 真实模型端到端验证

- 配置 `LLM_API_KEY` 后跑通首次真实 DeepAgents Build（规划→生成→pytest-cov≥80%→Vitest→Vite build→修复闭环），按真实模型行为调优 Prompt 与门禁
- 真实跑通智能体对话（聊天模式 + 工具模式：写文件/沙箱/HITL 审批）与 AI 流程生成

### P1 · 即将完成

- CI 工作流入库（文件已就绪，等具备 workflows 权限的账号推送）
- 对话记忆语义向量召回在真实网关上的联调（当前降级关键词+重要度排序，功能可用）

### P2 · 生产级加固

- Playwright E2E 实跑、SAST/镜像扫描/SBOM 接入 CI、大规模并发验收
- 固定域名、HTTPS 与蓝绿流量代理（含 Nginx TLS 模板）
- 多节点部署下的并发锁与队列水平扩展验证
- 审计日志可视化（管理后台）

### P3 · 企业重复性工作方向（底座已具备，需执行层）

- 通用 `agent_task` 执行链路：提交任务 → 选 Agent/Skill → 沙箱执行 → 结果/审批/通知（复用对话工具模式与流程编排）
- 文档处理 Skills：Excel/PDF 字段抽取、清洗比对、报表生成
- 定时/触发调度：cron、Webhook 触发重复任务
- 企业连接器：IMAP 邮箱、企微/钉钉机器人、数据库只读适配器
- 业务任务模板库：常见重复工作沉淀为一键复用模板

---

## 当前边界

已实现核心能力，但以下内容仍需部署环境或后续增强：

- 真实模型 Key 未配置时不能运行 DeepAgents Build 与智能体对话/流程生成（接口会明确返回 503，绝不 Mock）
- 尚未进行真实模型的端到端首跑验证（当前全部验证基于脚本化模型与真实质量门禁）
- CI 工作流文件已准备好，但需具备 workflows 权限的账号推送入库后才会自动执行
- Playwright E2E 用例与一键脚本已就绪，需可下载 Chromium 的网络环境实跑
- SAST（Semgrep）、镜像扫描（Trivy）、SBOM（Syft）与并发压测（Locust）脚手架已提供，实跑需对应工具与 Docker daemon
- 企业微信专用 OAuth 与钉钉专用消息格式尚未单独封装
- Docker 部署使用动态端口，尚未接入固定域名、HTTPS 和蓝绿流量代理
- 本地进程沙箱不提供可靠网络/文件系统边界，生产必须使用 Docker Sandbox
- 生成应用 PostgreSQL 回滚依赖部署机器安装 `pg_dump` 和 `pg_restore`
- 平台 Docker 镜像与 `docker-compose.production.yml` 已在无 Docker 环境做静态校验，首次使用时请在具备 Docker daemon 的机器上完成镜像构建验证

---

## License

当前项目用于产品原型和企业内部研发验证。正式开源或商业发布前，请补充许可证、第三方依赖合规和安全审计说明。
