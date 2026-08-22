import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api, ApiError } from '../../api/client'
import UsersPage from './UsersPage.vue'

vi.mock('../../api/client', () => ({
  ApiError: class extends Error {
    status: number
    code: string
    details: Record<string, unknown>
    constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
      super(message)
      this.status = status
      this.code = code
      this.details = details
    }
  },
  api: {
    adminUsers: vi.fn(),
    me: vi.fn(),
    updateAdminUser: vi.fn(),
    createAdminUser: vi.fn(),
    deleteAdminUser: vi.fn(),
  },
}))

const USERS = [
  { id: 'u1', email: 'admin@company.com', displayName: '周明远', department: '信息技术部', platformRole: 'super_admin', isActive: true, authSource: 'local', lastLoginAt: null, createdAt: '2026-08-19T00:00:00Z', projectCount: 2 },
  { id: 'u2', email: 'lin.jia@company.com', displayName: '林嘉', department: '人力资源部', platformRole: 'user', isActive: false, authSource: 'local', lastLoginAt: '2026-08-19T08:00:00Z', createdAt: '2026-08-19T00:00:00Z', projectCount: 4 },
]

function mockAdminUsers() {
  vi.mocked(api.adminUsers).mockResolvedValue(USERS)
  vi.mocked(api.me).mockResolvedValue({ id: 'u1', email: 'admin@company.com', displayName: '周明远', platformRole: 'super_admin', department: '信息技术部', isActive: true, authSource: 'local', lastLoginAt: null })
}

async function mountPage() {
  const wrapper = mount(UsersPage, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('UsersPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockAdminUsers()
  })

  it('从真实 API 渲染用户列表与统计', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('周明远')
    expect(wrapper.text()).toContain('admin@company.com')
    expect(wrapper.text()).toContain('lin.jia@company.com')
    expect(wrapper.text()).toContain('人力资源部')
    // 平台用户统计 = 2
    const metrics = wrapper.findAll('.admin-metrics article')
    expect(metrics[0].find('strong').text()).toBe('2')
    expect(vi.mocked(api.adminUsers)).toHaveBeenCalledTimes(1)
  })

  it('角色下拉变更调用 updateAdminUser 并刷新行', async () => {
    vi.mocked(api.updateAdminUser).mockResolvedValue({ ...USERS[1], platformRole: 'platform_admin' })
    const wrapper = await mountPage()
    const selects = wrapper.findAll('select.role-select')
    expect(selects).toHaveLength(2)
    await selects[1].setValue('platform_admin')
    expect(vi.mocked(api.updateAdminUser)).toHaveBeenCalledWith('u2', { platformRole: 'platform_admin' })
    await flushPromises()
    expect(wrapper.text()).toContain('平台管理员')
  })

  it('启停开关调用 updateAdminUser', async () => {
    vi.mocked(api.updateAdminUser).mockResolvedValue({ ...USERS[1], isActive: true })
    const wrapper = await mountPage()
    const toggles = wrapper.findAll('.toggle-control')
    await toggles[1].trigger('click')
    expect(vi.mocked(api.updateAdminUser)).toHaveBeenCalledWith('u2', { isActive: true })
  })

  it('当前账号的开关与删除按钮被禁用', async () => {
    const wrapper = await mountPage()
    const toggles = wrapper.findAll('.toggle-control')
    expect(toggles[0].attributes('disabled')).toBeDefined()
    const deleteButtons = wrapper.findAll('button.danger-ghost')
    expect(deleteButtons[0].attributes('disabled')).toBeDefined()
  })

  it('删除流程：确认弹窗 → deleteAdminUser → 行移除', async () => {
    vi.mocked(api.deleteAdminUser).mockResolvedValue(undefined)
    const wrapper = await mountPage()
    await wrapper.findAll('button.danger-ghost')[1].trigger('click')
    expect(wrapper.text()).toContain('删除平台用户')
    const confirm = wrapper.findAll('footer.dialog-foot button').find(button => button.text().includes('确认删除'))
    expect(confirm).toBeDefined()
    await confirm!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.deleteAdminUser)).toHaveBeenCalledWith('u2')
    await flushPromises()
    expect(wrapper.text()).not.toContain('lin.jia@company.com')
  })

  it('创建用户：填写表单 → createAdminUser → 展示一次性初始密码', async () => {
    const created = { id: 'u3', email: 'new.hire@company.com', displayName: '新员工', department: 'IT', platformRole: 'user', isActive: true, authSource: 'local', lastLoginAt: null, createdAt: '2026-08-20T00:00:00Z', projectCount: 0 }
    vi.mocked(api.createAdminUser).mockResolvedValue({ user: created, tempPassword: 'Temp12345678' })
    const wrapper = await mountPage()
    await wrapper.find('button.button.primary').trigger('click')
    await wrapper.find('.dialog div.form-input input').setValue('new.hire@company.com')
    const formInputs = wrapper.findAll('.dialog input.form-input')
    await formInputs[0].setValue('新员工')
    await formInputs[1].setValue('IT')
    const createButton = wrapper.findAll('footer.dialog-foot button').find(button => button.text().includes('创建用户'))
    await createButton!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createAdminUser)).toHaveBeenCalledWith(expect.objectContaining({ email: 'new.hire@company.com', displayName: '新员工', department: 'IT', platformRole: 'user' }))
    await flushPromises()
    expect(wrapper.text()).toContain('new.hire@company.com')
  })

  it('API 失败时展示错误信息', async () => {
    vi.mocked(api.adminUsers).mockRejectedValue(new ApiError(403, 'PLATFORM_ADMIN_REQUIRED', '需要平台管理员权限'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('需要平台管理员权限')
  })
})
