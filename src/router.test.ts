import { beforeEach, describe, expect, it } from 'vitest'
import router from './router'

describe('router', () => {
  beforeEach(() => localStorage.clear())

  it('注册了 OIDC 回调路由并使用 blank 布局', () => {
    const route = router.resolve('/login/callback')
    expect(route.matched).toHaveLength(1)
    expect(route.meta.layout).toBe('blank')
  })

  it('注册了管理后台全部路由', () => {
    expect(router.resolve('/admin/agent-types/new').matched).toHaveLength(1)
    expect(router.resolve('/admin/skills').matched).toHaveLength(1)
    expect(router.resolve('/admin/pipeline-templates').matched).toHaveLength(1)
    expect(router.resolve('/admin/users').meta.title).toBe('用户与权限')
    expect(router.resolve('/admin/resources').matched).toHaveLength(1)
    expect(router.resolve('/admin/settings').matched).toHaveLength(1)
  })

  it('未登录访问受保护页面时重定向到登录页并携带 redirect', async () => {
    await router.push('/projects')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/projects')
  })

  it('回调页不受登录守卫拦截', async () => {
    await router.push('/login/callback?code=c&state=s')
    expect(router.currentRoute.value.path).toBe('/login/callback')
    expect(router.currentRoute.value.query.code).toBe('c')
  })

  it('已登录后访问 /login 会跳回工作空间', async () => {
    localStorage.setItem('agent_platform_access_token', 'token')
    await router.push('/projects')
    expect(router.currentRoute.value.path).toBe('/projects')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/projects')
  })

  it('未匹配路径回退到项目空间', () => {
    const route = router.resolve('/no/such/page')
    expect(route.matched).toHaveLength(1)
    expect(route.matched[0]?.redirect).toBe('/projects')
  })
})
