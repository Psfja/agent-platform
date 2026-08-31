import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, authTokens } from './client'

function jsonResponse(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response
}

function b64url(payload: object): string {
  // 标准 base64（客户端会自行做 -/_ 还原），与 authTokens.role 的 atob 解析兼容
  return btoa(JSON.stringify(payload))
}

const tokenResponse = {
  accessToken: 'access-1',
  refreshToken: 'refresh-1',
  tokenType: 'bearer',
  expiresIn: 1800,
  user: { id: 'u1', email: 'a@company.com', displayName: '甲', platformRole: 'user', department: 'IT', isActive: true, authSource: 'local', lastLoginAt: null },
}

describe('authTokens', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => localStorage.clear())

  it('保存、读取和清除令牌', () => {
    expect(authTokens.access()).toBe('')
    authTokens.set('a', 'r')
    expect(authTokens.access()).toBe('a')
    expect(authTokens.refresh()).toBe('r')
    authTokens.clear()
    expect(authTokens.access()).toBe('')
    expect(authTokens.refresh()).toBe('')
  })

  it('从 JWT 载荷解析平台角色', () => {
    const token = `header.${b64url({ role: 'platform_admin', sub: 'u1' })}.signature`
    authTokens.set(token, 'r')
    expect(authTokens.role()).toBe('platform_admin')
  })

  it('畸形令牌解析失败时返回空角色', () => {
    authTokens.set('not-a-jwt', 'r')
    expect(authTokens.role()).toBe('')
  })
})

describe('ApiError', () => {
  it('携带状态码、错误码、消息与详情', () => {
    const error = new ApiError(503, 'LLM_NOT_CONFIGURED', '未配置模型密钥', { hint: 'check env' })
    expect(error).toBeInstanceOf(Error)
    expect(error.status).toBe(503)
    expect(error.code).toBe('LLM_NOT_CONFIGURED')
    expect(error.message).toBe('未配置模型密钥')
    expect(error.details).toEqual({ hint: 'check env' })
  })
})

describe('api 请求路径与方法', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  beforeEach(() => {
    localStorage.clear()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('oidcCallback 换取令牌并写入本地存储', async () => {
    fetchMock.mockResolvedValue(jsonResponse(tokenResponse))
    const result = await api.oidcCallback('auth-code', 'state-token')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/sso/oidc/callback', expect.objectContaining({ method: 'POST', body: JSON.stringify({ code: 'auth-code', state: 'state-token' }) }))
    expect(result.accessToken).toBe('access-1')
    expect(authTokens.access()).toBe('access-1')
    expect(authTokens.refresh()).toBe('refresh-1')
  })

  it('oidcStart 请求开始授权端点', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ authorizationUrl: 'https://idp.example.com/authorize?x=1', state: 's' }))
    const result = await api.oidcStart()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/sso/oidc/start', expect.anything())
    expect(result.authorizationUrl).toContain('idp.example.com')
  })

  it('agentTypes / pipelineTemplates 访问管理端点', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))
    await api.agentTypes()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/agent-types', expect.anything())
    await api.pipelineTemplates()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/pipeline-templates', expect.anything())
  })

  it('createAgentType / updateAgentType / deleteAgentType', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 't1' }))
    await api.createAgentType({ name: 'sec', displayName: '安全', description: 'desc', systemPrompt: 'p', model: 'm', temperature: 0.2, tools: [], skills: [], sandboxConfig: {}, isActive: true })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/agent-types', expect.objectContaining({ method: 'POST' }))
    await api.updateAgentType('t1', { isActive: false })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/agent-types/t1', expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ isActive: false }) }))
    fetchMock.mockResolvedValue(jsonResponse(undefined, 204))
    await api.deleteAgentType('t1')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/agent-types/t1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('createPipelineTemplate / updatePipelineTemplate', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'p1' }))
    await api.createPipelineTemplate({ name: 'flow', displayName: '流程', description: 'd', templateType: 'custom', isActive: true, nodes: [] })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/pipeline-templates', expect.objectContaining({ method: 'POST' }))
    await api.updatePipelineTemplate('p1', { displayName: '流程2', description: 'd', templateType: 'custom', isActive: false, nodes: [] })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/pipeline-templates/p1', expect.objectContaining({ method: 'PUT' }))
  })

  it('adminUsers 增删改查', async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ id: 'u1' }]))
    await api.adminUsers()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/users', expect.anything())
    await api.createAdminUser({ email: 'n@company.com', displayName: '新', department: '', platformRole: 'user' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/users', expect.objectContaining({ method: 'POST' }))
    await api.updateAdminUser('u1', { isActive: false })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/users/u1', expect.objectContaining({ method: 'PATCH' }))
    fetchMock.mockResolvedValue(jsonResponse(undefined, 204))
    await api.deleteAdminUser('u1')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/users/u1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('monitoringSummary / settingsStatus / integrationsStatus', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ queue: {} }))
    await api.monitoringSummary()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/monitoring/summary', expect.anything())
    await api.settingsStatus()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/settings/status', expect.anything())
    await api.integrationsStatus()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/integrations/status', expect.anything())
  })

  it('登录成功保存令牌；失败抛出 ApiError', async () => {
    fetchMock.mockResolvedValue(jsonResponse(tokenResponse))
    await api.login('a@company.com', 'pw')
    expect(authTokens.access()).toBe('access-1')
    fetchMock.mockResolvedValue(jsonResponse({ error: { code: 'INVALID_CREDENTIALS', message: '密码错误', details: {} } }, 401))
    await expect(api.login('a@company.com', 'bad')).rejects.toBeInstanceOf(ApiError)
  })
})
