import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../../api/client'
import AgentTypeEditPage from './AgentTypeEditPage.vue'

const { routeState, routerPush } = vi.hoisted(() => ({
  routeState: { params: { id: 'new' } as Record<string, string>, query: {} as Record<string, string> },
  routerPush: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => routeState, useRouter: () => ({ push: routerPush }) }))
vi.mock('../../api/client', () => ({
  ApiError: class extends Error { status = 0; code = ''; details: Record<string, unknown> = {} },
  api: {
    skills: vi.fn(),
    agentType: vi.fn(),
    createAgentType: vi.fn(),
    updateAgentType: vi.fn(),
  },
}))

const SKILLS = [
  { name: 'requirement-analysis', displayName: '需求分析', version: '1.0.0', description: '分析需求', entrypoint: 'main.py', instructions: 'i', agentTypes: [], tags: [], inputSchema: {}, path: '/skills/requirement-analysis', executable: true, checksum: 'abc' },
  { name: 'code-metrics', displayName: '代码度量', version: '1.0.0', description: '度量代码', entrypoint: 'main.py', instructions: 'i', agentTypes: [], tags: [], inputSchema: {}, path: '/skills/code-metrics', executable: true, checksum: 'def' },
]

const EXISTING = { id: 'a1', name: 'backend-developer', displayName: '后端开发工程师', description: 'FastAPI 服务开发', systemPrompt: '你是后端工程师。', model: 'deepseek-coder', temperature: 0.2, tools: ['read_file'], skills: ['code-metrics'], sandboxConfig: { cpu: 2, memoryMb: 512 }, version: 3, isTemplate: true, isActive: true, usage: { pipelineNodes: 0, templateNames: [], activeTasks: 0 }, createdAt: '2026-08-19T00:00:00Z', updatedAt: '2026-08-19T00:00:00Z' }

async function mountPage() {
  const wrapper = mount(AgentTypeEditPage, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('AgentTypeEditPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerPush.mockClear()
    routeState.params = { id: 'new' }
    routeState.query = {}
    vi.mocked(api.skills).mockResolvedValue(SKILLS)
  })

  it('创建模式：填写表单 → createAgentType → 返回列表', async () => {
    vi.mocked(api.createAgentType).mockResolvedValue(EXISTING)
    const wrapper = await mountPage()
    // 基础信息
    await wrapper.find('input[placeholder="backend-developer"]').setValue('security-reviewer')
    await wrapper.find('input[placeholder="后端开发工程师"]').setValue('安全审查工程师')
    await wrapper.find('textarea').setValue('检查鉴权、输入与依赖风险')
    // 系统提示词
    await wrapper.findAll('.agent-edit-tabs button')[1].trigger('click')
    await wrapper.find('.prompt-textarea').setValue('你是企业安全审查工程师。')
    // Skills 从真实 Registry 装配
    await wrapper.findAll('.agent-edit-tabs button')[2].trigger('click')
    expect(wrapper.text()).toContain('需求分析')
    await wrapper.findAll('.chip-grid.skills .chip-check')[0].find('input').setValue(true)
    // 保存
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createAgentType)).toHaveBeenCalledWith(expect.objectContaining({
      name: 'security-reviewer',
      displayName: '安全审查工程师',
      description: '检查鉴权、输入与依赖风险',
      systemPrompt: '你是企业安全审查工程师。',
      skills: expect.arrayContaining(['requirement-analysis']),
    }))
    expect(routerPush).toHaveBeenCalledWith('/admin/agent-types')
  })

  it('编辑模式：加载现有配置并 PATCH 更新', async () => {
    routeState.params = { id: 'a1' }
    vi.mocked(api.agentType).mockResolvedValue(EXISTING)
    vi.mocked(api.updateAgentType).mockResolvedValue({ ...EXISTING, version: 4 })
    const wrapper = await mountPage()
    expect(vi.mocked(api.agentType)).toHaveBeenCalledWith('a1')
    expect((wrapper.find('input[placeholder="backend-developer"]').element as HTMLInputElement).value).toBe('backend-developer')
    expect(wrapper.text()).toContain('v3')
    await wrapper.find('textarea').setValue('新的职责说明')
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.updateAgentType)).toHaveBeenCalledWith('a1', expect.objectContaining({ description: '新的职责说明', isActive: true }))
    expect(routerPush).toHaveBeenCalledWith('/admin/agent-types')
  })

  it('保存失败时展示后端错误信息', async () => {
    vi.mocked(api.createAgentType).mockRejectedValue(new Error('智能体类型标识已存在'))
    const wrapper = await mountPage()
    await wrapper.find('input[placeholder="backend-developer"]').setValue('dup')
    await wrapper.find('input[placeholder="后端开发工程师"]').setValue('重复')
    await wrapper.find('textarea').setValue('描述内容描述内容')
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('智能体类型标识已存在')
    expect(routerPush).not.toHaveBeenCalled()
  })
})
