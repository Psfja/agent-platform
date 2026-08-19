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
export interface AgentBuildRecord { id: string; projectId: string; iterationId: string | null; requirement: string; template: string; mode: 'initial' | 'incremental'; baseBuildId: string | null; model: string; status: string; currentStage: string; progress: number; plan: Record<string, any>; generatedFiles: { path: string; size: number; sha256?: string }[]; changedFilesCount: number; coverage: number | null; testResults: { name: string; command: string[]; passed: boolean; status: string; exitCode: number | null; stdout: string; stderr: string; elapsedMs: number; attempt: number; coverage?: number }[]; attempt: number; maxFixAttempts: number; promptTokens: number; completionTokens: number; workspacePath: string; artifactPath: string; errorMessage: string; cancellationRequested: boolean; startedAt: string | null; finishedAt: string | null; createdAt: string; updatedAt: string; logs: AgentBuildLog[] }
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
  createAgentBuild(projectId: string, payload: { requirement: string; template: 'fullstack'; mode?: 'initial' | 'incremental'; baseBuildId?: string; autoDeploy?: boolean; deployEnvironment?: 'test' | 'production'; model?: string; maxFixAttempts: number; iterationId?: string }): Promise<AgentBuildRecord> {
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
  connectEvents(projectId: string, onEvent: (event: MessageEvent) => void): EventSource {
    const source = new EventSource(`${API_BASE}/projects/${projectId}/events?access_token=${encodeURIComponent(authTokens.access())}`)
    for (const event of ['task.status_changed', 'task.created', 'iteration.started', 'project.updated']) source.addEventListener(event, onEvent)
    return source
  },
}
