import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../../api/client'
import AgentTypesPage from './AgentTypesPage.vue'

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('../../api/client', () => ({
  api: {
    agentTypes: vi.fn(),
    updateAgentType: vi.fn(),
    deleteAgentType: vi.fn(),
  },
}))

const AGENTS = [
  { id: 'a1', name: 'backend-developer', displayName: '后端开发工程师', description: 'FastAPI 服务、业务逻辑与数据库访问实现', systemPrompt: 'prompt', model: 'deepseek-coder', tools: ['read_file', 'write_file', 'shell'], skills: ['code-metrics'], sandboxConfig: {}, version: 3, isTemplate: true, isActive: true, createdAt: '2026-08-19T00:00:00Z', updatedAt: '2026-08-19T00:00:00Z' },
  { id: 'a2', name: 'test-engineer', displayName: '测试工程师', description: '单元、集成与回归测试生成及执行', systemPrompt: 'prompt', model: 'qwen-max', tools: ['shell'], skills: [], sandboxConfig: {}, version: 1, isTemplate: false, isActive: false, createdAt: '2026-08-19T00:00:00Z', updatedAt: '2026-08-19T00:00:00Z' },
]

async function mountPage() {
  const wrapper = mount(AgentTypesPage, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('AgentTypesPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerPush.mockClear()
    vi.mocked(api.agentTypes).mockResolvedValue(AGENTS)
  })

  it('从真实 API 渲染智能体类型与统计', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('后端开发工程师')
    expect(wrapper.text()).toContain('backend-developer')
    expect(wrapper.text()).toContain('deepseek-coder')
    expect(wrapper.text()).toContain('测试工程师')
    const metrics = wrapper.findAll('.admin-metrics article')
    expect(metrics[0].find('strong').text()).toBe('2') // 智能体类型总数
    expect(metrics[1].find('strong').text()).toBe('1') // 已启用
  })

  it('搜索过滤智能体列表', async () => {
    const wrapper = await mountPage()
    await wrapper.find('input[placeholder*="搜索"]').setValue('测试')
    expect(wrapper.text()).toContain('测试工程师')
    expect(wrapper.text()).not.toContain('后端开发工程师')
  })

  it('启停开关调用 updateAgentType 并刷新行', async () => {
    vi.mocked(api.updateAgentType).mockResolvedValue({ ...AGENTS[0], isActive: false, version: 4 })
    const wrapper = await mountPage()
    await wrapper.find('.toggle-control').trigger('click')
    expect(vi.mocked(api.updateAgentType)).toHaveBeenCalledWith('a1', { isActive: false })
    await flushPromises()
    expect(wrapper.text()).toContain('v4')
  })

  it('删除流程：确认弹窗 → deleteAgentType → 行移除', async () => {
    vi.mocked(api.deleteAgentType).mockResolvedValue(undefined)
    const wrapper = await mountPage()
    await wrapper.findAll('button.danger-ghost')[0].trigger('click')
    expect(wrapper.text()).toContain('删除智能体类型')
    const confirm = wrapper.findAll('footer.dialog-foot button').find(button => button.text().includes('确认删除'))
    await confirm!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.deleteAgentType)).toHaveBeenCalledWith('a1')
    await flushPromises()
    expect(wrapper.text()).not.toContain('backend-developer')
  })

  it('删除被引用智能体失败时保留行并提示', async () => {
    vi.mocked(api.deleteAgentType).mockRejectedValue(new Error('智能体类型正在被流程或任务使用'))
    const wrapper = await mountPage()
    await wrapper.findAll('button.danger-ghost')[0].trigger('click')
    const confirm = wrapper.findAll('footer.dialog-foot button').find(button => button.text().includes('确认删除'))
    await confirm!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('backend-developer')
  })

  it('创建按钮跳转到新建页面', async () => {
    const wrapper = await mountPage()
    await wrapper.find('button.button.primary').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/admin/agent-types/new')
  })
})
