import type { Iteration, Project, Task } from '../types'

const API_BASE = '/api/v1'
const ACCESS_KEY = 'agent_platform_access_token'
const REFRESH_KEY = 'agent_platform_refresh_token'

export const authTokens = {
  access: () => localStorage.getItem(ACCESS_KEY) || '',
  refresh: () => localStorage.getItem(REFRESH_KEY) || '',
  set: (access: string, refresh: string) => { localStorage.setItem(ACCESS_KEY, access); localStorage.setItem(REFRESH_KEY, refresh) },
  clear: () => { localStorage.removeItem(ACCESS_KEY); localStorage.removeItem(REFRESH_KEY) },
  role: () => { try { return JSON.parse(atob((localStorage.getItem(ACCESS_KEY)||'').split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))).role || '' } catch { return '' } },
}

export class ApiError extends Error {
  status: number
  code: string
  details: Record<string, unknown>
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, options: RequestInit = {}, allowRefresh = true): Promise<T> {
  const token = authTokens.access()
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  if (response.status === 401 && allowRefresh && !path.startsWith('/auth/')) {
    const refreshToken = authTokens.refresh()
    if (refreshToken) {
      const refreshed = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refreshToken }) })
      if (refreshed.ok) {
        const payload = await refreshed.json()
        authTokens.set(payload.accessToken, payload.refreshToken)
        return request<T>(path, options, false)
      }
    }
    authTokens.clear()
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = payload.error || payload.detail || {}
    throw new ApiError(response.status, error.code || 'HTTP_ERROR', error.message || `请求失败 (${response.status})`, error.details || {})
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function formatRelative(iso: string): string {
  const timestamp = new Date(iso).getTime()
  if (!Number.isFinite(timestamp)) return iso
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`
  if (minutes < 2880) return '昨天'
  return `${Math.floor(minutes / 1440)} 天前`
}

interface ApiProject extends Omit<Project, 'updatedAt'> { updatedAt: string }
interface ApiTask extends Omit<Task, 'startedAt'> { startedAt: string | null }
interface ApiIteration extends Omit<Iteration, 'date'> { date: string; impactAnalysis?: Record<string, unknown> }

function mapProject(project: ApiProject): Project { return { ...project, updatedAt: formatRelative(project.updatedAt) } }
function mapTask(task: ApiTask): Task { return { ...task, startedAt: task.startedAt ? new Date(task.startedAt).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '待执行' } }
function mapIteration(item: ApiIteration): Iteration { return { ...item, date: new Date(item.date).toLocaleString('zh-CN', { hour12: false }) } }

export interface AuthUser { id: string; email: string; displayName: string; platformRole: string; department: string; isActive: boolean; authSource: string; lastLoginAt: string | null }
export interface AuthTokenResponse { accessToken: string; refreshToken: string; tokenType: string; expiresIn: number; user: AuthUser }
export interface ProjectMemberRecord { id: string; userId: string; email: string; displayName: string; department: string; role: string; status: string; joinedAt: string }
export interface AgentTypeRecord { id: string; name: string; displayName: string; description: string; systemPrompt: string; model: string; temperature: number; tools: string[]; skills: string[]; sandboxConfig: Record<string, any>; version: number; isTemplate: boolean; isActive: boolean; usage: { pipelineNodes: number; templateNames: string[]; activeTasks: number }; createdAt: string; updatedAt: string }
export interface PipelineNodeRecord { nodeKey: string; agentTypeId: string; displayName: string; dependsOn: string[]; executionMode: 'sequential' | 'parallel'; config: Record<string, unknown>; position: number }
export interface PipelineTemplateRecord { id: string; name: string; displayName: string; description: string; templateType: string; version: number; isActive: boolean; isSystem: boolean; config: Record<string, unknown>; nodes: PipelineNodeRecord[]; createdAt: string; updatedAt: string }
export interface PipelineDraftRecord { name: string; displayName: string; description: string; templateType: string; nodes: PipelineNodeRecord[] }
export interface AdminUserRecord { id: string; email: string; displayName: string; department: string; platformRole: string; isActive: boolean; authSource: string; lastLoginAt: string | null; createdAt: string; projectCount: number; ownedProjects: number }
export interface MonitoringSummary {
  system: { cpuPercent: number; memoryPercent: number; diskPercent: number; loadAverage: number[] }
  projects: { total: number; active: number }
  tasks: { running: number; failed: number }
  agentBuilds: { completed: number; failed: number; tokens: number }
  deployments: { running: number; failed: number }
  queue: { redisAvailable: boolean; queueName: string; fallbackThreads: boolean; counts: Record<string, number> }
  storage: { provider: string; configured: boolean }
}
export interface IntegrationsStatus {
  git: { configured: boolean; remote: string }
  minio: { configured: boolean; endpoint: string; bucket: string }
  smtp: { configured: boolean; host: string }
  webhook: { configured: boolean }
}
export interface SettingsStatus {
  platform: { name: string; environment: string; debug: boolean }
  database: { engine: string; migrationsEnabled: boolean }
  llm: { configured: boolean; baseUrl: string; model: string; engine: string; timeoutSeconds: number; maxRetries: number }
  sandbox: { configuredBackend: string; activeBackend: string; available: boolean; isolation: string; dockerAvailable: boolean; limits: Record<string, number | string>; warnings: string[] }
  queue: { redisAvailable: boolean; queueName: string; fallbackThreads: boolean; counts: Record<string, number> }
  sso: { oidc: { configured: boolean; issuer: string; clientId: string }; ldap: { configured: boolean; url: string; baseDn: string } }
  security: { jwtAlgorithm: string; accessTokenMinutes: number; refreshTokenDays: number }
  storage: { minio: { configured: boolean; endpoint: string; bucket: string; secure: boolean } }
  git: { configured: boolean; remote: string; defaultBranch: string }
  notifications: { smtp: { configured: boolean; host: string; port: number; username: string }; webhook: { configured: boolean } }
  deployment: { publicHost: string; generatedDatabaseConfigured: boolean }
  generatedAt: string
}
export interface ConversationRecord { id: string; projectId: string; agentKey: string; mode: string; title: string; createdAt: string; updatedAt: string; lastMessageAt: string | null; messageCount: number }
export interface ConversationMessageRecord { id: string; role: 'user' | 'assistant'; content: string; metadata: Record<string, any>; createdAt: string }
export interface ConversationDetailRecord extends ConversationRecord { messages: ConversationMessageRecord[] }
export interface ChatTurnRecord {
  conversation: ConversationRecord
  userMessage: ConversationMessageRecord
  assistantMessage: ConversationMessageRecord
  memoriesUsed: MemoryRecord[]
  context: { historyMessages: number; droppedMessages: number; estimatedTokens: number; budgetTokens: number; memoriesRecalled: number; skillsLoaded: number }
}
export interface StreamDoneRecord {
  conversation: ConversationRecord
  assistantMessage?: ConversationMessageRecord | null
  memoriesUsed: MemoryRecord[]
  userMessageId?: string
  title?: string | null
  interrupt?: { toolName: string; payload: Record<string, any> } | null
}
export interface ConversationInterruptRecord { id: string; conversationId: string; toolName: string; payload: Record<string, any>; status: string; createdAt: string }

export interface RequirementRecord { id:string;projectId:string;version:number;title:string;contentMarkdown:string;structuredData:Record<string,any>;status:string;changeSummary:string;createdBy:string|null;createdAt:string }
export interface DocumentRecord { id:string;projectId:string;documentType:string;version:number;title:string;contentMarkdown:string;sourceBuildId:string|null;metadata:Record<string,any>;createdBy:string|null;createdAt:string;updatedAt:string }

export interface TaskLogRecord { id?: string; time: string; type: string; eventType?: string; text: string; metadata?: Record<string, unknown> }
export interface InterventionRecord { id: string; taskId: string; actorName: string; interventionType: string; content: string; status: string; agentResponse: string; createdAt: string; processedAt: string | null }
export interface ImpactAnalysisResult {
  iterationId: string
  proposedVersion: string
  riskLevel: 'low' | 'medium' | 'high'
  changeType: string
  summary: string
  modules: { name: string; change: string; risk: string }[]
  estimatedFiles: { min: number; max: number }
  databaseChange: boolean
  databaseStrategy: string
  existingApiImpact: boolean
  breakingChanges: string[]
  suggestedAgents: string[]
  estimatedTasks: number
  recommendations: string[]
}
export interface CompareResult {
  fromVersion: string; toVersion: string
  summary: { files: number; added: number; removed: number }
  files: { path: string; type: string; added: number; removed: number }[]
  schemaChanges: Record<string, unknown>[]
  apiChanges: Record<string, unknown>[]
  featureChanges: { added: string[]; removed: string[]; unchanged: string[] }
  hasBreakingChanges: boolean
}
export interface ArtifactRecord { id: string; name: string; type: string; path: string; sizeBytes: number; metadata: Record<string, unknown>; createdAt: string }
export interface MemoryRecord { id: string; projectId: string; agentKey: string; scope: string; memoryType: string; key: string; content: string; importance: number; tags: string[]; metadata: Record<string, unknown>; accessCount: number; lastAccessedAt: string | null; expiresAt: string | null; createdAt: string; updatedAt: string }
export interface SkillRecord { name: string; displayName: string; version: string; description: string; entrypoint: string | null; instructions: string; agentTypes: string[]; tags: string[]; inputSchema: Record<string, unknown>; path: string; executable: boolean; checksum: string }
export interface SandboxStatus { configuredBackend: string; activeBackend: string; available: boolean; isolation: string; dockerAvailable: boolean; limits: Record<string, number | string>; warnings: string[] }
export interface SandboxRunRecord { id: string; projectId: string; taskId: string | null; skillName: string | null; backend: string; language: string; command: string[]; status: string; exitCode: number | null; stdout: string; stderr: string; input: Record<string, unknown>; result: Record<string, unknown>; resourceUsage: Record<string, unknown>; errorMessage: string; startedAt: string | null; finishedAt: string | null; createdAt: string }
export interface AgentContextRecord { projectId: string; agentKey: string; memories: MemoryRecord[]; skills: SkillRecord[]; memoryPrompt: string; skillPrompt: string; sandbox: SandboxStatus }
export interface LLMBuildStatus { configured: boolean; provider: string; baseUrl: string; model: string; timeoutSeconds: number; supportsRealExecution: boolean; message: string; agentEngine:string; nativeDeepagents:boolean }
export interface AgentBuildLog { id: string; stage: string; level: string; agentKey: string | null; message: string; metadata: Record<string, unknown>; createdAt: string }
export interface AgentBuildRecord { id: string; projectId: string; iterationId: string | null; requirement: string; template: string; mode: 'initial' | 'incremental'; baseBuildId: string | null; model: string; temperature: number; status: string; currentStage: string; progress: number; plan: Record<string, any>; generatedFiles: { path: string; size: number; sha256?: string }[]; changedFilesCount: number; coverage: number | null; testResults: { name: string; command: string[]; passed: boolean; status: string; exitCode: number | null; stdout: string; stderr: string; elapsedMs: number; attempt: number; coverage?: number }[]; attempt: number; maxFixAttempts: number; promptTokens: number; completionTokens: number; workspacePath: string; artifactPath: string; errorMessage: string; cancellationRequested: boolean; startedAt: string | null; finishedAt: string | null; createdAt: string; updatedAt: string; logs: AgentBuildLog[] }
export interface AgentBuildFile { path: string; size: number; content?: string | null }
export interface DeploymentRuntimeStatus { dockerAvailable: boolean; dockerVersion: string; ready: boolean; message: string; runningDeployments: number }
export interface DeploymentRuntimeLog { id: string; stage: string; level: string; message: string; metadata: Record<string, unknown>; createdAt: string }
export interface ApplicationDeploymentRecord { id: string; projectId: string; buildId: string; environment: 'test' | 'production'; version: string; status: string; currentStage: string; progress: number; backendImage: string; frontendImage: string; backendContainer: string; frontendContainer: string; networkName: string; hostPort: number | null; deployUrl: string; healthUrl: string; smokeResult: Record<string, any>; resourceLimits: Record<string, any>; previousDeploymentId: string | null; rollbackOfId: string | null; errorMessage: string; startedAt: string | null; finishedAt: string | null; createdAt: string; updatedAt: string; logs: DeploymentRuntimeLog[] }

export const api = {
  async login(email: string, password: string): Promise<AuthTokenResponse> {
    const result = await request<AuthTokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }, false)
    authTokens.set(result.accessToken, result.refreshToken)
    return result
  },
  me(): Promise<AuthUser> { return request('/auth/me') },
  ssoStatus(): Promise<{oidcConfigured:boolean;ldapConfigured:boolean;providers:string[]}> { return request('/auth/sso/status', {}, false) },
  oidcStart(): Promise<{authorizationUrl:string;state:string}> { return request('/auth/sso/oidc/start', {}, false) },
  async oidcCallback(code: string, state: string): Promise<AuthTokenResponse> {
    const result = await request<AuthTokenResponse>('/auth/sso/oidc/callback', { method: 'POST', body: JSON.stringify({ code, state }) }, false)
    authTokens.set(result.accessToken, result.refreshToken)
    return result
  },
  async ldapLogin(username:string,password:string): Promise<AuthTokenResponse> { const result=await request<AuthTokenResponse>('/auth/sso/ldap',{method:'POST',body:JSON.stringify({username,password})},false);authTokens.set(result.accessToken,result.refreshToken);return result },
  async logout(): Promise<void> {
    const refreshToken = authTokens.refresh()
    try { if (refreshToken) await request('/auth/logout', { method: 'POST', body: JSON.stringify({ refreshToken }) }, false) } finally { authTokens.clear() }
  },
  projectMembers(projectId: string): Promise<ProjectMemberRecord[]> { return request(`/projects/${projectId}/members`) },
  addProjectMember(projectId: string, email: string, role: string): Promise<ProjectMemberRecord> { return request(`/projects/${projectId}/members`, { method: 'POST', body: JSON.stringify({ email, role }) }) },
  removeProjectMember(projectId: string, userId: string): Promise<void> { return request(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' }) },
  requirements(projectId:string):Promise<RequirementRecord[]>{return request(`/projects/${projectId}/requirements`)},
  saveRequirement(projectId:string,payload:{title:string;contentMarkdown:string;structuredData?:Record<string,any>;status?:string;changeSummary?:string}):Promise<RequirementRecord>{return request(`/projects/${projectId}/requirements`,{method:'POST',body:JSON.stringify(payload)})},
  documents(projectId:string):Promise<DocumentRecord[]>{return request(`/projects/${projectId}/documents`)},
  saveDocument(projectId:string,payload:{documentType:string;title:string;contentMarkdown:string;sourceBuildId?:string;metadata?:Record<string,any>}):Promise<DocumentRecord>{return request(`/projects/${projectId}/documents`,{method:'POST',body:JSON.stringify(payload)})},
  uploadAttachment(projectId:string,file:File):Promise<Record<string,any>>{const form=new FormData();form.append('file',file);return request(`/projects/${projectId}/attachments`,{method:'POST',body:form,headers:{}})},
  async projects(search = ''): Promise<Project[]> {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    return (await request<ApiProject[]>(`/projects${query}`)).map(mapProject)
  },
  async project(id: string): Promise<Project> { return mapProject(await request<ApiProject>(`/projects/${id}`)) },
  async createProject(payload: { name: string; description: string; template: string; autoBuild?: boolean }): Promise<Project> {
    return mapProject(await request<ApiProject>('/projects', { method: 'POST', body: JSON.stringify(payload) }))
  },
  async projectAction(id: string, action: 'pause' | 'resume' | 'archive' | 'restore'): Promise<Project> {
    return mapProject(await request<ApiProject>(`/projects/${id}/actions`, { method: 'POST', body: JSON.stringify({ action }) }))
  },
  async tasks(projectId: string, taskType?: string): Promise<Task[]> {
    const query = taskType ? `?task_type=${encodeURIComponent(taskType)}` : ''
    return (await request<ApiTask[]>(`/projects/${projectId}/tasks${query}`)).map(mapTask)
  },
  async task(projectId: string, taskId: string): Promise<Task> { return mapTask(await request<ApiTask>(`/projects/${projectId}/tasks/${taskId}`)) },
  async taskAction(projectId: string, taskId: string, action: 'pause' | 'resume' | 'cancel' | 'retry'): Promise<Task> {
    return mapTask(await request<ApiTask>(`/projects/${projectId}/tasks/${taskId}/actions`, { method: 'POST', body: JSON.stringify({ action }) }))
  },
  logs(projectId: string, taskId: string): Promise<TaskLogRecord[]> { return request(`/projects/${projectId}/tasks/${taskId}/logs`) },
  interventions(projectId: string, taskId: string): Promise<InterventionRecord[]> { return request(`/projects/${projectId}/tasks/${taskId}/interventions`) },
  intervene(projectId: string, taskId: string, content: string, interventionType = 'instruction'): Promise<InterventionRecord> {
    return request(`/projects/${projectId}/tasks/${taskId}/interventions`, { method: 'POST', body: JSON.stringify({ content, interventionType }) })
  },
  async iterations(projectId: string): Promise<Iteration[]> { return (await request<ApiIteration[]>(`/projects/${projectId}/iterations`)).map(mapIteration) },
  async iteration(projectId: string, iterationId: string): Promise<Iteration> { return mapIteration(await request<ApiIteration>(`/projects/${projectId}/iterations/${iterationId}`)) },
  analyze(projectId: string, changeRequest: string): Promise<ImpactAnalysisResult> {
    return request(`/projects/${projectId}/iterations/impact-analysis`, { method: 'POST', body: JSON.stringify({ changeRequest }) })
  },
  confirmIteration(projectId: string, iterationId: string): Promise<ApiIteration> {
    return request(`/projects/${projectId}/iterations/${iterationId}/confirm`, { method: 'POST', body: JSON.stringify({ approved: true }) })
  },
  compare(projectId: string, from: string, to: string): Promise<CompareResult> {
    return request(`/projects/${projectId}/versions/compare?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`)
  },
  rollback(projectId: string, version: string, confirmDataRisk = false): Promise<{ operationId: string; targetVersion: string; status: string; steps: string[] }> {
    return request(`/projects/${projectId}/versions/${encodeURIComponent(version)}/rollback`, { method: 'POST', body: JSON.stringify({ confirmDataRisk }) })
  },
  artifacts(projectId: string, type?: string): Promise<ArtifactRecord[]> {
    return request(`/projects/${projectId}/artifacts${type ? `?type=${encodeURIComponent(type)}` : ''}`)
  },
  skills(agentKey?: string): Promise<SkillRecord[]> {
    return request(`/skills${agentKey ? `?agent_key=${encodeURIComponent(agentKey)}` : ''}`)
  },
  reloadSkills(): Promise<SkillRecord[]> { return request('/skills/reload', { method: 'POST' }) },
  memories(projectId: string, params: { agentKey?: string; memoryType?: string; search?: string } = {}): Promise<MemoryRecord[]> {
    const query = new URLSearchParams()
    if (params.agentKey) query.set('agent_key', params.agentKey)
    if (params.memoryType) query.set('memory_type', params.memoryType)
    if (params.search) query.set('search', params.search)
    return request(`/projects/${projectId}/memories${query.size ? `?${query}` : ''}`)
  },
  createMemory(projectId: string, payload: { agentKey: string; scope: string; memoryType: string; key: string; content: string; importance: number; tags: string[] }): Promise<MemoryRecord> {
    return request(`/projects/${projectId}/memories`, { method: 'POST', body: JSON.stringify(payload) })
  },
  deleteMemory(projectId: string, memoryId: string): Promise<void> { return request(`/projects/${projectId}/memories/${memoryId}`, { method: 'DELETE' }) },
  agentTypes(): Promise<AgentTypeRecord[]> { return request('/admin/agent-types') },
  agentType(id: string): Promise<AgentTypeRecord> { return request(`/admin/agent-types/${id}`) },
  createAgentType(payload: { name: string; displayName: string; description: string; systemPrompt: string; model: string; temperature: number; tools: string[]; skills: string[]; sandboxConfig: Record<string, any>; isActive: boolean }): Promise<AgentTypeRecord> { return request('/admin/agent-types', { method: 'POST', body: JSON.stringify(payload) }) },
  updateAgentType(id: string, payload: Partial<{ displayName: string; description: string; systemPrompt: string; model: string; temperature: number; tools: string[]; skills: string[]; sandboxConfig: Record<string, any>; isActive: boolean }>): Promise<AgentTypeRecord> { return request(`/admin/agent-types/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }) },
  deleteAgentType(id: string): Promise<void> { return request(`/admin/agent-types/${id}`, { method: 'DELETE' }) },
  pipelineTemplates(): Promise<PipelineTemplateRecord[]> { return request('/admin/pipeline-templates') },
  createPipelineTemplate(payload: { name: string; displayName: string; description: string; templateType: 'fullstack' | 'api' | 'frontend' | 'custom'; isActive: boolean; nodes: PipelineNodeRecord[] }): Promise<PipelineTemplateRecord> { return request('/admin/pipeline-templates', { method: 'POST', body: JSON.stringify(payload) }) },
  updatePipelineTemplate(id: string, payload: { displayName: string; description: string; templateType: 'fullstack' | 'api' | 'frontend' | 'custom'; isActive: boolean; nodes: PipelineNodeRecord[] }): Promise<PipelineTemplateRecord> { return request(`/admin/pipeline-templates/${id}`, { method: 'PUT', body: JSON.stringify(payload) }) },
  generatePipeline(requirement: string): Promise<{ draft: PipelineDraftRecord; warnings: string[] }> { return request('/admin/pipeline-templates/generate', { method: 'POST', body: JSON.stringify({ requirement }) }) },
  adminUsers(): Promise<AdminUserRecord[]> { return request('/admin/users') },
  createAdminUser(payload: { email: string; displayName: string; department: string; platformRole: string; initialPassword?: string }): Promise<{ user: AdminUserRecord; tempPassword: string | null }> { return request('/admin/users', { method: 'POST', body: JSON.stringify(payload) }) },
  updateAdminUser(id: string, payload: Partial<{ displayName: string; department: string; platformRole: string; isActive: boolean; newPassword: string }>): Promise<AdminUserRecord> { return request(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }) },
  deleteAdminUser(id: string, reassign = false): Promise<void> { return request(`/admin/users/${id}`, { method: 'DELETE', body: JSON.stringify({ reassign }) }) },
  monitoringSummary(): Promise<MonitoringSummary> { return request('/monitoring/summary') },
  integrationsStatus(): Promise<IntegrationsStatus> { return request('/integrations/status') },
  settingsStatus(): Promise<SettingsStatus> { return request('/settings/status') },
  notifications(): Promise<{ id: string; eventType: string; title: string; content: string; status: string; readAt: string | null; createdAt: string }[]> { return request('/notifications') },
  readNotification(id: string): Promise<{ ok: boolean }> { return request(`/notifications/${id}/read`, { method: 'POST' }) },
  sandboxStatus(): Promise<SandboxStatus> { return request('/sandbox/status') },
  sandboxRuns(projectId: string): Promise<SandboxRunRecord[]> { return request(`/projects/${projectId}/sandbox/runs`) },
  runSandbox(projectId: string, code: string, stdin = '', timeoutSeconds = 30): Promise<SandboxRunRecord> {
    return request(`/projects/${projectId}/sandbox/runs`, { method: 'POST', body: JSON.stringify({ language: 'python', code, stdin, timeoutSeconds }) })
  },
  executeSkill(projectId: string, skillName: string, input: Record<string, unknown>, rememberResult = true): Promise<SandboxRunRecord> {
    return request(`/projects/${projectId}/skills/${encodeURIComponent(skillName)}/execute`, { method: 'POST', body: JSON.stringify({ input, rememberResult }) })
  },
  agentContext(projectId: string, agentKey: string, query = ''): Promise<AgentContextRecord> {
    return request(`/projects/${projectId}/agents/${encodeURIComponent(agentKey)}/context${query ? `?query=${encodeURIComponent(query)}` : ''}`)
  },
  agentBuildStatus(): Promise<LLMBuildStatus> { return request('/agent-build/status') },
  agentBuilds(projectId: string): Promise<AgentBuildRecord[]> { return request(`/projects/${projectId}/agent-builds`) },
  createAgentBuild(projectId: string, payload: { requirement: string; template: 'fullstack'; mode?: 'initial' | 'incremental'; baseBuildId?: string; autoDeploy?: boolean; deployEnvironment?: 'test' | 'production'; model?: string; maxFixAttempts: number; temperature?: number; iterationId?: string }): Promise<AgentBuildRecord> {
    return request(`/projects/${projectId}/agent-builds`, { method: 'POST', body: JSON.stringify(payload) })
  },
  agentBuild(projectId: string, buildId: string): Promise<AgentBuildRecord> { return request(`/projects/${projectId}/agent-builds/${buildId}`) },
  cancelAgentBuild(projectId: string, buildId: string): Promise<AgentBuildRecord> { return request(`/projects/${projectId}/agent-builds/${buildId}/cancel`, { method: 'POST' }) },
  instructAgentBuild(projectId: string, buildId: string, content: string): Promise<AgentBuildLog> { return request(`/projects/${projectId}/agent-builds/${buildId}/instructions`, { method: 'POST', body: JSON.stringify({ content }) }) },
  decideBuildHitl(projectId:string,buildId:string,decision:'approve'|'reject'|'edit',reason=''):Promise<AgentBuildRecord>{return request(`/projects/${projectId}/agent-builds/${buildId}/hitl`,{method:'POST',body:JSON.stringify({decision,reason})})},
  retryAgentBuild(projectId: string, buildId: string): Promise<AgentBuildRecord> { return request(`/projects/${projectId}/agent-builds/${buildId}/retry`, { method: 'POST' }) },
  agentBuildFiles(projectId: string, buildId: string): Promise<AgentBuildFile[]> { return request(`/projects/${projectId}/agent-builds/${buildId}/files`) },
  agentBuildFile(projectId: string, buildId: string, path: string): Promise<AgentBuildFile> { return request(`/projects/${projectId}/agent-builds/${buildId}/file?path=${encodeURIComponent(path)}`) },
  agentBuildDownloadUrl(projectId: string, buildId: string): string { return `${API_BASE}/projects/${projectId}/agent-builds/${buildId}/download?access_token=${encodeURIComponent(authTokens.access())}` },
  deploymentRuntimeStatus(): Promise<DeploymentRuntimeStatus> { return request('/deployment-runtime/status') },
  applicationDeployments(projectId: string): Promise<ApplicationDeploymentRecord[]> { return request(`/projects/${projectId}/application-deployments`) },
  applicationDeployment(projectId: string, deploymentId: string): Promise<ApplicationDeploymentRecord> { return request(`/projects/${projectId}/application-deployments/${deploymentId}`) },
  createApplicationDeployment(projectId: string, buildId: string, environment: 'test' | 'production' = 'test'): Promise<ApplicationDeploymentRecord> { return request(`/projects/${projectId}/application-deployments`, { method: 'POST', body: JSON.stringify({ buildId, environment }) }) },
  stopApplicationDeployment(projectId: string, deploymentId: string): Promise<ApplicationDeploymentRecord> { return request(`/projects/${projectId}/application-deployments/${deploymentId}/stop`, { method: 'POST' }) },
  rollbackApplicationDeployment(projectId: string, deploymentId: string): Promise<ApplicationDeploymentRecord> { return request(`/projects/${projectId}/application-deployments/${deploymentId}/rollback`, { method: 'POST' }) },
  deploymentContainerLogs(projectId: string, deploymentId: string): Promise<{backend:string;frontend:string}> { return request(`/projects/${projectId}/application-deployments/${deploymentId}/container-logs`) },
  queueStatus(): Promise<{redisAvailable:boolean;redisUrl:string;queueName:string;fallbackThreads:boolean;counts:Record<string,number>}> { return request('/queue/status') },
  migrationStatus(): Promise<{currentRevision:string|null;headRevision:string|null;upToDate:boolean;enabled:boolean}> { return request('/queue/migrations') },
  conversations(projectId: string, agentKey?: string): Promise<ConversationRecord[]> {
    return request(`/projects/${projectId}/conversations${agentKey ? `?agent_key=${encodeURIComponent(agentKey)}` : ''}`)
  },
  createConversation(projectId: string, agentKey: string, title = ''): Promise<ConversationRecord> { return request(`/projects/${projectId}/conversations`, { method: 'POST', body: JSON.stringify({ agentKey, title }) }) },
  conversation(projectId: string, conversationId: string): Promise<ConversationDetailRecord> { return request(`/projects/${projectId}/conversations/${conversationId}`) },
  renameConversation(projectId: string, conversationId: string, title: string): Promise<ConversationRecord> { return request(`/projects/${projectId}/conversations/${conversationId}`, { method: 'PATCH', body: JSON.stringify({ title }) }) },
  deleteConversation(projectId: string, conversationId: string): Promise<void> { return request(`/projects/${projectId}/conversations/${conversationId}`, { method: 'DELETE' }) },
  sendConversationMessage(projectId: string, conversationId: string, content: string, remember = true): Promise<ChatTurnRecord> { return request(`/projects/${projectId}/conversations/${conversationId}/messages`, { method: 'POST', body: JSON.stringify({ content, remember }) }) },
  async streamConversationMessage(
    projectId: string,
    conversationId: string,
    content: string,
    remember: boolean,
    handlers: {
      onMeta?: (context: Record<string, number | string>) => void
      onDelta?: (chunk: string) => void
      onTitle?: (title: string) => void
      onInterrupt?: (interrupt: { interruptId?: string; toolName: string; payload: Record<string, any> }) => void
    } = {},
  ): Promise<StreamDoneRecord> {
    const doFetch = (token: string) => fetch(`${API_BASE}/projects/${projectId}/conversations/${conversationId}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ content, remember }),
    })
    let response = await doFetch(authTokens.access())
    if (response.status === 401) {
      const refreshToken = authTokens.refresh()
      if (refreshToken) {
        const refreshed = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refreshToken }) })
        if (refreshed.ok) {
          const payload = await refreshed.json()
          authTokens.set(payload.accessToken, payload.refreshToken)
          response = await doFetch(payload.accessToken)
        }
      }
      if (response.status === 401) {
        authTokens.clear()
        window.location.assign('/login')
        throw new ApiError(401, 'AUTH_REQUIRED', '登录已过期')
      }
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      const error = payload.error || payload.detail || {}
      throw new ApiError(response.status, error.code || 'HTTP_ERROR', error.message || `请求失败 (${response.status})`, error.details || {})
    }
    if (!response.body) throw new Error('当前浏览器不支持流式响应')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let done: StreamDoneRecord | null = null
    const handleEvent = (raw: string) => {
      const dataLine = raw.split('\n').find(line => line.startsWith('data:'))
      if (!dataLine) return
      const parsed = JSON.parse(dataLine.slice(5).trim()) as { type: string; [key: string]: any }
      if (parsed.type === 'meta') handlers.onMeta?.(parsed.context)
      else if (parsed.type === 'delta') handlers.onDelta?.(parsed.content || '')
      else if (parsed.type === 'title') handlers.onTitle?.(parsed.title)
      else if (parsed.type === 'interrupt') handlers.onInterrupt?.({ interruptId: parsed.interruptId, toolName: parsed.toolName, payload: parsed.payload })
      else if (parsed.type === 'done') done = parsed as unknown as StreamDoneRecord
      else if (parsed.type === 'error') throw new ApiError(parsed.status || 502, parsed.code || 'STREAM_ERROR', parsed.message || '流式对话失败')
    }
    try {
      while (true) {
        const { value, done: finished } = await reader.read()
        if (finished) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const part of parts) {
          const trimmed = part.trim()
          if (trimmed) handleEvent(trimmed)
        }
      }
      buffer += decoder.decode()
      if (buffer.trim()) handleEvent(buffer.trim())
    } finally {
      reader.releaseLock()
    }
    if (!done) throw new ApiError(502, 'STREAM_INCOMPLETE', '流式响应未完成')
    return done
  },
  regenerateConversationTitle(projectId: string, conversationId: string): Promise<ConversationRecord> { return request(`/projects/${projectId}/conversations/${conversationId}/title`, { method: 'POST' }) },
  setConversationMode(projectId: string, conversationId: string, mode: 'chat' | 'agent'): Promise<ConversationRecord> { return request(`/projects/${projectId}/conversations/${conversationId}`, { method: 'PATCH', body: JSON.stringify({ mode }) }) },
  conversationInterrupts(projectId: string, conversationId: string): Promise<ConversationInterruptRecord[]> { return request(`/projects/${projectId}/conversations/${conversationId}/interrupts`) },
  decideConversationInterrupt(projectId: string, conversationId: string, interruptId: string, decision: 'approve' | 'edit' | 'reject', reason = '', editedAction: Record<string, any> = {}): Promise<{ conversation: ConversationRecord; assistantMessage: ConversationMessageRecord }> { return request(`/projects/${projectId}/conversations/${conversationId}/interrupts/${interruptId}/decide`, { method: 'POST', body: JSON.stringify({ decision, reason, editedAction }) }) },
  conversationWorkspace(projectId: string, conversationId: string): Promise<{ files: { path: string; size: number }[] }> { return request(`/projects/${projectId}/conversations/${conversationId}/workspace`) },
  connectEvents(projectId: string, onEvent: (event: MessageEvent) => void): EventSource {
    const source = new EventSource(`${API_BASE}/projects/${projectId}/events?access_token=${encodeURIComponent(authTokens.access())}`)
    for (const event of ['task.status_changed', 'task.created', 'iteration.started', 'project.updated']) source.addEventListener(event, onEvent)
    return source
  },
}
