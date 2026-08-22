import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../api/client'
import LoginCallbackPage from './LoginCallbackPage.vue'

const { routeState, routerReplace } = vi.hoisted(() => ({
  routeState: { query: {} as Record<string, string> },
  routerReplace: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => routeState, useRouter: () => ({ replace: routerReplace }) }))
vi.mock('../api/client', () => ({
  authTokens: { access: () => '', refresh: () => '', set: vi.fn(), clear: vi.fn(), role: () => '' },
  api: { oidcCallback: vi.fn(), me: vi.fn() },
}))

describe('LoginCallbackPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerReplace.mockClear()
    routeState.query = {}
  })
  afterEach(() => vi.useRealTimers())

  it('用 code + state 换取令牌并跳转工作空间', async () => {
    vi.useFakeTimers()
    routeState.query = { code: 'auth-code', state: 'state-token' }
    vi.mocked(api.oidcCallback).mockResolvedValue({ accessToken: 'a', refreshToken: 'r', tokenType: 'bearer', expiresIn: 1800, user: { id: 'u1', email: 'x@company.com', displayName: 'X', platformRole: 'user', department: '', isActive: true, authSource: 'oidc', lastLoginAt: null } })
    const wrapper = mount(LoginCallbackPage, { global: { plugins: [createPinia()] } })
    await vi.advanceTimersByTimeAsync(0)
    expect(vi.mocked(api.oidcCallback)).toHaveBeenCalledWith('auth-code', 'state-token')
    expect(wrapper.text()).toContain('认证成功')
    await vi.advanceTimersByTimeAsync(600)
    expect(routerReplace).toHaveBeenCalledWith('/projects')
  })

  it('身份提供商返回 error 时展示失败且不调用换取接口', async () => {
    routeState.query = { error: 'access_denied', error_description: '用户拒绝了授权' }
    const wrapper = mount(LoginCallbackPage, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('单点登录失败')
    expect(wrapper.text()).toContain('用户拒绝了授权')
    expect(vi.mocked(api.oidcCallback)).not.toHaveBeenCalled()
  })

  it('缺少 code/state 时提示参数缺失', async () => {
    routeState.query = { code: 'only-code' }
    const wrapper = mount(LoginCallbackPage, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('OIDC 回调参数缺失')
    expect(vi.mocked(api.oidcCallback)).not.toHaveBeenCalled()
  })

  it('换取失败时展示错误与返回登录按钮', async () => {
    routeState.query = { code: 'c', state: 's' }
    vi.mocked(api.oidcCallback).mockRejectedValue(new Error('OIDC state 无效或已过期'))
    const wrapper = mount(LoginCallbackPage, { global: { plugins: [createPinia()] } })
    await flushPromises()
    await flushPromises()
    expect(wrapper.text()).toContain('OIDC state 无效或已过期')
    await wrapper.findAll('button').find(button => button.text().includes('返回登录页'))!.trigger('click')
    expect(routerReplace).toHaveBeenCalledWith('/login')
  })
})
