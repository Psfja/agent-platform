# 智构（Agent Studio）差距分析报告

> 对比基准：仓库根目录 `README.md`（依据《企业智能体平台 PRD V1.2》的能力清单）
> 审计方式：逐项核对代码、实际运行后端测试/前端构建、无外部依赖冒烟启动、API 与页面逐一比对
> 审计日期：2026-08-20 · 分支 `arena/01a01ced-agent-platform`
>
> **修复记录（2026-08-20）**：第二节三大缺口已全部修复，见文末「修复记录」。

---

## 〇、修复记录（2026-08-20）

三大缺口（P0×2 + 仓库卫生）已在本次会话修复并验证：

### 1. 企业 OIDC 前端闭环 ✅
- 新增 `src/pages/LoginCallbackPage.vue`：处理 IdP 回调（code/state/error）、调用换取接口、成功跳转、失败提示
- `src/router.ts` 新增 `/login/callback` 路由（blank 布局，绕过登录守卫）
- `src/api/client.ts` 新增 `oidcCallback(code, state)`，与 `.env.example` 中 `OIDC_REDIRECT_URI` 对齐

### 2. 管理后台接入真实 API ✅
- **后端新增** `backend/app/api/admin_users.py`：`GET/POST/PATCH/DELETE /api/v1/admin/users`
  - 列表含项目参与数；创建支持自动生成初始密码（一次性返回）；角色变更/启停/密码重置/删除均有保护（不能动自己、超级管理员受保护、拥有项目的用户不可删）；全部写审计日志；平台管理员不能授予/降级超管
- **后端新增** `GET /api/v1/settings/status`（operations.py）：脱敏的平台配置状态（LLM/数据库/沙箱/队列/SSO/存储/Git/通知/部署），供设置页真实展示
- **前端重写 6 个管理页**，全部读取真实 API、具备完整交互：
  - `AgentTypesPage`：真实列表/搜索/启停（PATCH）/删除（带保护提示）
  - `AgentTypeEditPage`：真实创建与编辑（名称/提示词/模型/工具/Skills 多选/沙箱参数），Skills 从真实 Registry 加载
  - `PipelineTemplatesPage`：真实模板列表/启停（PUT）/创建（含节点构建器，引用真实 AgentType）
  - `UsersPage`：真实用户列表/角色下拉变更/启停/重置密码/创建（显示一次性初始密码）/删除
  - `SettingsPage`：五个标签页展示真实配置状态（脱敏，标注只读）
  - `ResourcesPage`：真实 CPU/内存/磁盘/项目/任务/构建 Token/部署/队列/存储状态
- 新增集成测试 `test_admin_user_management_and_settings_status`，后端测试 **21 → 22 passed**

### 3. 仓库卫生 ✅
- 新增根目录 `.gitignore`（node_modules/dist/.venv/__pycache__/backend/data/.env/tsbuildinfo 等）
- `git rm --cached` 移除 119 个误提交的运行期文件（沙箱、Checkpoint SQLite、上传附件、tsbuildinfo），工作区文件保留

验证：`pytest` 22 passed；`npm run build`（vue-tsc + Vite）通过；通过 Vite 代理端到端冒烟（登录 → agent-types/pipeline-templates/settings-status/admin-users 全部返回真实数据，非管理员访问 403）。

### 第二轮修复（2026-08-20）：P1 三项原「中等缺口」4/5/6 已补齐：

#### 4. CI 流水线 ✅
- 新增 `.github/workflows/ci.yml`：push/PR 触发
  - backend job：Python 3.11 + `pip install -r requirements-dev.txt` + `alembic heads` 单 head 校验 + `pytest`
  - frontend job：Node 22 + `npm ci` + `npm run test`（Vitest）+ `npm run build`（vue-tsc + Vite）+ `npm audit --audit-level=moderate`
- 本地已逐步模拟 CI 命令验证（alembic heads、npm ci、全部测试与构建通过）

#### 5. 平台自身 Docker 部署产物 ✅
- `backend/docker/platform-api.Dockerfile`：API/Worker 单镜像，python:3.11-slim，非 root 运行，启动时自动 `alembic upgrade head`
- `docker/frontend.Dockerfile` + `docker/nginx.conf`：Vue 构建 + Nginx（SPA 回退、`/api` `/health` 反向代理、SSE 关闭缓冲、`/healthz` 探活）
- `docker-compose.production.yml`：PostgreSQL 16 + Redis 7 + API + Worker + 前端 + 可选 MinIO（`--profile storage`），健康检查、依赖顺序、重启策略、数据卷、42 项环境变量锚点
- 根目录 `.env.docker.example`（全部部署变量模板，JWT_SECRET 必改标注）
- `.dockerignore` ×2（根目录与 backend），YAML 语法已用 PyYAML 解析校验
- 注意：沙箱无 Docker daemon，镜像未实际构建；README 已标注需在部署环境完成构建验证

#### 6. 平台前端 Vitest 测试 ✅
- 引入 `vitest@3.2.7`（3.2.4 存在 GHSA-5xrq-8626-4rwp 严重公告，已升级修复）、`@vue/test-utils`、`jsdom`
- `package.json` 新增 `npm run test`（vitest run）；`vite.config.ts` 增加 test 配置
- 新增 6 个测试文件、38 个用例：
  - `src/api/client.test.ts`（14）：authTokens、ApiError、OIDC 换取/开始、管理端点路径与方法、登录与错误
  - `src/pages/admin/UsersPage.test.ts`（7）：真实渲染、角色变更、启停、自保护、删除、创建（一次性密码）、错误态
  - `src/pages/admin/AgentTypesPage.test.ts`（6）：渲染统计、搜索、启停、删除、删除失败保留、跳转创建
  - `src/pages/admin/AgentTypeEditPage.test.ts`（3）：创建提交、编辑回填与 PATCH、失败提示
  - `src/pages/LoginCallbackPage.test.ts`（4）：成功换取+跳转、IdP 拒绝、参数缺失、换取失败
  - `src/router.test.ts`（6）：OIDC 回调 blank 路由、管理路由注册、登录守卫、回调豁免、登录跳转、404 回退
- 全部通过：`38 passed`；vue-tsc 类型检查与生产构建通过；`npm audit` 0 漏洞

---

## 一、结论概述

后端核心闭环（项目→需求→DeepAgents 构建→质量门禁→部署→迭代→HITL）**实现质量高，README 声称的后端能力基本全部属实且可运行**；项目的主要欠缺集中在**前端管理后台与真实 API 的接线、企业 SSO 的前端闭环、仓库工程卫生、以及 README 自认的"当前边界"** 上。

实测验证通过：

| 验证项 | 结果 |
|---|---|
| 后端集成测试 | ✅ `21 passed`（与 README 一致） |
| 前端 TypeScript 检查 + Vite Production Build | ✅ 通过 |
| `npm audit --audit-level=moderate` | ✅ 0 vulnerabilities |
| Alembic 迁移 | ✅ `0003_content_integrations (head)`，启动自动升级正常 |
| 无 Redis/PostgreSQL/MinIO/模型 Key 冷启动 | ✅ `/health`、`/metrics`、登录、SSO 状态均正常返回 |

---

## 二、严重缺口（README 声称可用，实际未闭环）

### 1. 企业 OIDC SSO 前端没有回调页面 —— 登录闭环断裂 ⛔

- README 与 `backend/.env.example` 均写明 `OIDC_REDIRECT_URI=http://localhost:4173/login/callback`。
- 但前端 `src/router.ts` **没有 `/login/callback` 路由**，`src/api/client.ts` 也**没有调用 `POST /api/v1/auth/sso/oidc/callback` 的方法**。
- `LoginPage.vue` 只有 `startOIDC()`（跳转到 IdP），授权码回调回来后前端无处接收，后端虽然实现了完整的 Discovery/JWKS/授权码换取/自动预配，**从前端看 OIDC 登录永远无法完成**。
- 影响：README「认证与权限 → 通用 OIDC Discovery、JWKS 和授权码回调」在前端侧是断的。

### 2. 管理后台大部分页面是静态 Demo，没有接真实后端 API ⛔

后端 API（`/api/v1/admin/agent-types`、`/pipeline-templates`、`/monitoring/summary` 等）完整存在且测试通过，但前端页面基本是写死的演示数据：

| 页面 | 行数 | API 调用 | 现状 |
|---|---|---|---|
| `AgentTypesPage.vue`（智能体管理） | 13 | ❌ 0 | 写死 8 个智能体；"启用/停用"只弹 toast |
| `AgentTypeEditPage.vue`（创建/编辑智能体） | 16 | ❌ 0 | **保存按钮只弹 toast 后跳转，不调用任何 API**，"测试运行"按钮无行为 |
| `PipelineTemplatesPage.vue`（流程编排） | 10 | ❌ 0 | 写死 4 个模板；"创建模板"只弹 toast |
| `UsersPage.vue`（用户与权限） | 10 | ❌ 0 | 写死 6 个用户；"发送邀请"只弹 toast。**后端根本没有用户管理 API**（`api/router.py` 无 users 端点），此功能前后端都缺失 |
| `ResourcesPage.vue`（资源监控） | 9 | ❌ 0 | 全部演示数据（README 已自认） |
| `SettingsPage.vue`（系统设置） | 15 | 仅 SSO 状态 | 保存只弹 toast；页面还展示了**实际不存在的功能**（如"AES-256 加密存储已启用"、伪造的 Gateway Key `sk-agent-platform-gateway-2026`） |
| `SkillsPage.vue`（Skill 管理） | 23 | ✅ 3 | 唯一真正接 API 的管理页 |

即：README「AgentType CRUD、配置版本历史、PipelineTemplate CRUD」等能力目前**只有后端，没有可用前端入口**（配置版本历史、执行数据等更是无页面展示）。

### 3. 仓库卫生：运行数据被提交进 Git，且没有 `.gitignore` ⛔

- 仓库**根目录没有 `.gitignore`**，`node_modules/`、`dist/`、`backend/.venv/` 全部裸奔。
- 已有 **119 个运行期文件被提交**到 Git：
  - `backend/data/langgraph_checkpoints.sqlite`（及其 `-shm`、`-wal` 运行时临时文件）
  - `backend/data/sandboxes/` 下 114 个沙箱工作区（含 stdout/stderr 日志）
  - `backend/data/uploads/` 演示附件
- 每次跑测试/启动服务都会产生新的未跟踪文件，会污染 `git status` 并持续膨胀仓库。

---

## 三、中等缺口

### 4. 没有 CI/CD 流水线

- 无 `.github/workflows/`。README「测试与验证」的命令（pytest / vue-tsc / vite build / npm audit）只能人工执行，代码门禁没有被自动化。

### 5. 平台自身没有容器化部署产物

- `backend/docker/` 只有生成应用的 `agent-build.Dockerfile`；平台 API、Redis Worker、前端**没有自己的 Dockerfile 和 docker-compose 生产编排**（只有 `docker-compose.infrastructure.yml` 管 PostgreSQL/Redis/MinIO）。
- 意味着"生成应用的部署"很完整，但"平台本身的部署"没有方案。

### 6. 平台前端没有任何自动化测试

- 全仓库没有 Vitest/组件测试/`.spec` 文件（README 中的 Vitest 只用于**生成的应用**，不覆盖平台前端）。
- 结合缺口 2（页面大量 mock），前端质量风险最高。

### 7. Prometheus 缺少 Token 指标（与 README 声称不符）

- README 声称 `/metrics` 输出"项目、任务、Agent Build、Deployment、Queue、**Token** 指标"。
- `monitoring.py` 实际只有前 5 类 Gauge，Token 用量只出现在 `GET /api/v1/monitoring/summary` 的 JSON 里，未暴露为 Prometheus 指标。

### 8. README 项目结构树已过时（文档不一致）

- 结构树遗漏了实际存在的 `api/artifacts.py`、`events.py`、`members.py`、`router.py`、`runtime.py`，以及 `services/agent_runtime.py`、`checkpointer.py`、`docker_runtime.py`、`event_bus.py`、`generated_workspace.py`、`impact_analyzer.py`、`llm_client.py`、`memory.py`、`migrations.py`、`orchestrator.py`、`sandbox.py`、`seed.py`、`skill_loader.py`、`versioning.py` 等文件。

---

## 四、README 自认、仍待补的边界（低优先/依赖部署环境）

以下为 README「当前边界」已声明，本次审计确认依旧缺失：

- Playwright E2E、SAST、镜像扫描、SBOM、大规模并发验收（无任何相关配置）
- 企业微信专用 OAuth、钉钉专用消息格式（`SettingsPage` 里的企微/钉钉开关是假数据）
- 固定域名、HTTPS、蓝绿流量代理（部署仍是动态端口）
- DeepAgents 原生 Checkpointer 仅 SQLite；`requirements.txt` 虽已装 `langgraph-checkpoint-postgres`，但 `checkpointer.py` 未实现 PostgreSQL 切换
- 生产必须强制 Docker 沙箱（当前本地进程沙箱仅资源限制）
- 无 LICENSE 文件（README 已提示）

---

## 五、建议的补齐顺序

1. **P0**：前端补 `/login/callback` 页面 + `client.ts` 的 `oidcCallback()`，打通企业 OIDC 登录闭环。
2. **P0**：把 `AgentTypesPage / AgentTypeEditPage / PipelineTemplatesPage` 接到已有的真实 API（含配置版本历史展示）；为 `UsersPage` 补齐后端用户管理 API（列表/角色/禁用/邀请）。
3. **P1**：补 `.gitignore`（node_modules、dist、.venv、`backend/data/**`、`__pycache__` 等），并从 Git 中移除已提交的运行数据。
4. **P1**：加 `.github/workflows/ci.yml`（pytest + vue-tsc + vite build + npm audit）。
5. **P1**：为平台前端引入 Vitest 组件测试（优先覆盖刚接线的管理页）。
6. **P2**：平台自身的 Dockerfile + compose 生产编排；`/metrics` 补 Token Gauge；更新 README 结构树；Settings/Resources 页接真实 API。

### 第三轮修复（2026-08-20）：前端功能冲突清零 + 假数据移除

系统排查前端全部页面后发现的"功能冲突/假数据冒充真实"问题，已全部修复：

| 冲突点 | 修复前 | 修复后 |
|---|---|---|
| 项目概览 DashboardPage | 展示 mock 任务树、假文案（"回归测试执行中·31 分钟"、98.7%）、暂停按钮只改本地状态 | 真实 project/tasks/builds/deployments 数据；暂停/继续调用 `projectAction` |
| 产物中心 ArtifactsPage | 假 v1.2.0/98.4%/468MB 静态数据，下载只弹 toast | 真实 artifacts 列表 + 部署状态 + 按 buildId 下载 ZIP |
| 代码仓库 CodePage | 对任何项目都显示 leave-hub 的假 approval.py 源码 | 从最新构建 generatedFiles 构建真实文件树，点击读取真实文件内容 |
| 项目文档 DocsPage | 假 ARCH-LEAVE-HUB v1.3.0 文档 | 真实 documents API（版本化），markdown 原文渲染 |
| 迭代详情 IterationDetailPage | 假任务/假 Diff/假测试报告 | 真实迭代 + 按 iterationId 关联的真实任务 + 影响分析 |
| 任务详情 TaskDetailPage | 假日志/假干预记录/假进度文案 | 真实 logs/interventions；暂停/继续/终止调用 taskAction；指令真实提交 |
| 任务树 TasksPage | mock 任务初始化、假"当前操作"文案 | 真实任务树；selected 空安全 |
| 迭代历史 IterationsPage | mock 迭代、硬编码 v1.2.0/98.4%、对比写死 v1.1.1 | 真实迭代；头部统计动态化；对比用真实上一版本 |
| 侧边栏 AppShell | 硬编码徽标"7/3"、假通知面板、假用量卡、'leave-hub'/'林嘉' fallback | 徽标/用量卡按管理员角色实时加载；通知面板接真实 /notifications（可标记已读） |
| 智能体管理 SkillsPage | 试运行硬编码项目 'leave-hub' | 项目下拉选择（默认第一个可访问项目） |
| 全局 mock 数据源 | `src/data/mock.ts` 被 4 处引用，后端故障时展示假项目 | 已删除；后端故障时展示空状态+错误提示 |

验证：前端 Vitest 42 passed（新增 DashboardPage 真实渲染/暂停测试）；vue-tsc + Vite 构建通过；端到端冒烟（登录 → 项目/任务/迭代/通知全部真实数据）。

**关于"不止软件开发"（企业重复性工作）的方向差距，见下方第五节。**

## 五、方向差距：从"AI 软件开发"到"企业重复性工作自动化"

当前平台的主闭环是"需求 → 生成软件"。要覆盖企业其他重复性工作（文档处理、数据抽取、报表生成、审批流转、巡检核对等），架构上已有大量可复用底座，缺的是"通用任务执行"这一层。

### 已有可复用的底座

- DeepAgents Supervisor/SubAgent 运行时（目前仅被 agent_builder 代码生成使用）
- Skill 注册表 + 沙箱执行（任意 Python/脚本能力包，天然适合"一个 Skill = 一类重复工作"）
- 持久记忆（按项目/Agent/重要度召回）、HITL 审批、Checkpoint 恢复
- Redis 队列 + Worker（只支持 agent_build / application_deployment 两种 Job）
- 附件上传与文本提取（PDF/MD/TXT/JSON/CSV/YAML）、通知（站内/SMTP/Webhook）

### 缺的六件事（按优先级）

1. **通用 Agent 任务执行 Job**：新增 `agent_task` 队列类型与 API（提交任务 → 选 Agent/Skill → 沙箱执行 → 结构化结果/产物 → HITL 审批 → 通知），UI 增加"任务工作台"。这是复用的核心枢纽。
2. **文档与数据处理 Skills**：Excel/Word/PDF 结构化抽取、字段清洗、去重比对、报表生成、翻译摘要；产出结果表（可下载 CSV/Excel）+ 差量报告。
3. **定时与触发调度**：cron/间隔/Webhook 触发重复任务（每周对账、每日报表、月度巡检），失败重试与告警。
4. **结果与人工闭环**：任务结果审查页（对照原文核对、批注、打回重跑），通用 HITL 已具备、缺结果展示层。
5. **企业连接器**：IMAP 邮箱、企微/钉钉机器人、数据库只读适配器、日历/ERP；现有 integrations 只有 SMTP/Webhook。
6. **任务模板库（Playbook）**：把常见重复工作沉淀为"模板 = Agent + Skills + 输入 Schema + 输出格式"，一键复用（类似 PipelineTemplate，但面向业务任务）。

### 建议落地方向（二选一）

- **A（快，验证价值）**：先做 1 + 2——通用 agent_task 执行链路 + 2~3 个文档类 Skill（发票/合同字段抽取、日报生成），配"任务工作台"页面。预计能直接跑通 80% 的文档类重复工作。
- **B（全）**：1~6 全部，但需要分 3 个迭代，且依赖部署环境的邮箱/IM 凭据。

建议先按 A 做一个垂直场景（例如"发票 OCR 字段抽取 + 台账生成"）验证端到端，再横向扩展 Skill 库。


### 第四轮修复（2026-08-20）：流程编排 AI 生成 + 可拖拽流程图

按用户要求补齐"流程编排"交互闭环：

- **后端 `POST /api/v1/admin/pipeline-templates/generate`**：自然语言需求 → 模型网关生成流程草稿。自动清洗非法标识/重复 nodeKey、剔除无效 AgentType 引用、清理自依赖与幽灵依赖、按依赖做 Kahn 拓扑排序；未配置 LLM_API_KEY 时返回 503 LLM_NOT_CONFIGURED（绝不 Mock）。新增 2 个集成测试（scripted model 全链路 + 未配置 503），后端 22 → 24 passed。
- **前端流程图编辑器（`FlowCanvas.vue` + `flowLayout.ts`）**：
  - SVG 流程图可视化：节点（Agent 图标 + 名称 + 顺序/并行标记）、依赖连线（并行用虚线标注）、箭头
  - 拖拽节点调整位置（画布坐标写入 node.config.canvas，随模板持久化）
  - 从节点右侧把手拖到另一节点左侧把手建立依赖（带环检测 `wouldCreateCycle`，环/重复/自依赖被拒绝）
  - 点击连线删除依赖、节点右上角 × 删除节点、添加节点、自动布局（按依赖深度分层）
  - 底部依赖面板勾选编辑、节点名称与执行模式编辑
- **页面（PipelineTemplatesPage）**：「AI 生成流程」对话框（示例需求 chips）→ 生成后进入流程图编辑器人工确认/调整 → 创建模板；现有模板可重新打开编辑器编辑（PUT 保存）
- 新增前端测试 11 个（flowLayout 纯函数 6 + 页面 AI 生成/保存/编辑/503 流程 5），前端 42 → 53 passed；vue-tsc + Vite 构建通过

### 第五轮修复（2026-08-20）：智能体对话 —— 长期记忆 + 上下文管理 + 多轮会话

按用户要求，为每个智能体补齐对话三要素：

- **对话功能**：新增 `conversations` / `conversation_messages` 表（Alembic 0004）。API：
  `POST/GET /projects/{id}/conversations`、`GET/PATCH/DELETE /projects/{id}/conversations/{cid}`、
  `POST /projects/{id}/conversations/{cid}/messages`。按项目 + 智能体隔离，标题自动取首条消息。
- **上下文管理**：每轮组装 `Agent 人设 + 按查询相关性召回的长期记忆 + 装配的 Skills 指令 + 历史消息`；
  Token 预算（`CONVERSATION_CONTEXT_TOKENS`，默认 6000）超出时裁剪最旧消息、保底保留最近
  `CONVERSATION_HISTORY_MIN_MESSAGES` 条；响应元数据返回 historyMessages/droppedMessages/estimatedTokens/memoriesRecalled。
- **长期记忆**：对话时召回（`MemoryService.retrieve` + `build_prompt`）；每轮回复后自动提取值得记住的事实
  写入 Episodic 记忆（带 `conversation` 标签，可开关 remember），下次对话自动召回。
- **LLM 接口**：`OpenAICompatibleClient` 新增普通 `chat()`（非 JSON）与 `estimate_tokens()`；未配置
  `LLM_API_KEY` 时返回 503 LLM_NOT_CONFIGURED，绝不 Mock 回复。
- **UI**：Agent 运行时页面新增「对话」标签页（ConversationPanel）：会话列表/新建/删除、消息气泡、
  输入发送（Enter 发送）、「对话提取记忆」开关、记忆召回与上下文统计条、503 配置指引。
- 修复过程中发现并修复真实 bug：记忆与 Skills 最初只"召回"未真正注入模型上下文，已修并加测试断言。
- 验证：后端 24 → 27 passed（scripted model 全链路 + 记忆提取 + 503 + token 估算）；前端 53 → 58 passed；
  vue-tsc + Vite 构建通过；端到端冒烟（迁移 0004 → 创建会话 → 无 Key 503 → 列表/详情）通过。

后续可增强：SSE 流式回复、会话标题 AI 生成、语义向量召回（当前为关键词+重要度）。

### 第六轮修复（2026-08-22）：对话 SSE 流式回复 + AI 会话标题

- **SSE 流式**：新增 `POST /projects/{id}/conversations/{cid}/messages/stream`
  事件序列 meta（上下文统计）→ delta*（逐 Token）→ title（可选）→ done（落库结果）｜error。
  使用可注入 session_factory（沿用 conftest 模式，测试库隔离）；Nginx/Vite 代理均已关闭缓冲。
- **打字机效果**：前端 `streamConversationMessage`（fetch + ReadableStream 解析，POST 无法用 EventSource），
  带 401 刷新重试；对话面板实时追加文本 + 光标闪烁；流式不可用时自动降级为普通请求。
- **AI 标题**：首条回复后自动用模型生成标题（失败降级为首句截断）；
  新增 `POST .../title` 端点 + 面板标题旁「魔法按钮」随时重生成（无消息 409，无 Key 503）。
- **LLM 接口**：`chat_stream()` 迭代器（提供方不支持 stream 时自动降级整段返回）。
- 修复过程中发现：SSE 错误事件的 AppError 字段提取错误（HTTPException 结构）、
  SSE 裸 dict 需手动 camelCase（不走 Pydantic 别名序列化）——均已修复并有测试覆盖。
- 验证：后端 27 → 29 passed；前端 58 → 60 passed；构建通过；
  端到端冒烟（Vite 代理 → meta 事件 + error 事件、content-type、标题 409）通过。
