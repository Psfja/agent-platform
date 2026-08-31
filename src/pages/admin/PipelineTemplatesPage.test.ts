import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../../api/client'
import PipelineTemplatesPage from './PipelineTemplatesPage.vue'

vi.mock('../../api/client', () => ({
  ApiError: class extends Error { status = 0; code = ''; details: Record<string, unknown> = {} },
  api: {
    pipelineTemplates: vi.fn(),
    agentTypes: vi.fn(),
    generatePipeline: vi.fn(),
    updatePipelineTemplate: vi.fn(),
    createPipelineTemplate: vi.fn(),
  },
}))
vi.mock('../../components/FlowCanvas.vue', () => ({
  default: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'select'],
    template: '<div class="flow-canvas-stub">{{ modelValue.length }} 节点</div>',
  },
}))

const AGENTS = [
  { id: 'a1', name: 'project-manager', displayName: '项目经理', description: '规划', systemPrompt: 'p', model: 'm', tools: [], skills: [], sandboxConfig: {}, version: 1, isTemplate: true, isActive: true, createdAt: '', updatedAt: '' },
  { id: 'a2', name: 'backend-developer', displayName: '后端开发工程师', description: '开发', systemPrompt: 'p', model: 'm', tools: [], skills: [], sandboxConfig: {}, version: 1, isTemplate: true, isActive: true, createdAt: '', updatedAt: '' },
]
const TEMPLATES = [
  { id: 't1', name: 'web-fullstack', displayName: 'Web 全栈应用', description: 'd', templateType: 'fullstack', version: 1, isActive: true, isSystem: true, config: {}, nodes: [], createdAt: '', updatedAt: '' },
]
const GENERATED_DRAFT = {
  draft: {
    name: 'invoice-audit-flow',
    displayName: '发票自动审核流程',
    description: '抽取发票字段并生成台账',
    templateType: 'custom',
    nodes: [
      { nodeKey: 'plan', agentTypeId: 'project-manager', displayName: '需求规划', dependsOn: [], executionMode: 'sequential', config: {}, position: 0 },
      { nodeKey: 'extract', agentTypeId: 'backend-developer', displayName: '字段抽取', dependsOn: ['plan'], executionMode: 'sequential', config: {}, position: 1 },
    ],
  },
  warnings: ['忽略了无效智能体引用：not-exists'],
}

async function mountPage() {
  const wrapper = mount(PipelineTemplatesPage, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('PipelineTemplatesPage · AI 生成与流程图编排', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.pipelineTemplates).mockResolvedValue(TEMPLATES as never)
    vi.mocked(api.agentTypes).mockResolvedValue(AGENTS as never)
  })

  it('列表渲染真实模板', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Web 全栈应用')
    expect(wrapper.text()).toContain('AI 生成流程')
    expect(wrapper.text()).toContain('手动创建')
  })

  it('AI 生成：输入需求 → generatePipeline → 打开流程图编辑器并显示节点与修正警告', async () => {
    vi.mocked(api.generatePipeline).mockResolvedValue(GENERATED_DRAFT as never)
    const wrapper = await mountPage()
    await wrapper.findAll('button').find(b => b.text().includes('AI 生成流程'))!.trigger('click')
    await wrapper.find('textarea.flow-requirement').setValue('员工报销单据自动审核，抽取发票字段并生成台账')
    await wrapper.findAll('button').find(b => b.text().includes('生成流程图'))!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.generatePipeline)).toHaveBeenCalledWith('员工报销单据自动审核，抽取发票字段并生成台账')
    // 编辑器打开：显示流程字段与画布节点数
    expect(wrapper.text()).toContain('流程编排编辑器')
    const fieldInputs = wrapper.findAll('.flow-fields input.form-input')
    expect((fieldInputs[1].element as HTMLInputElement).value).toBe('发票自动审核流程')
    expect(wrapper.text()).toContain('2 节点')
    expect(wrapper.text()).toContain('忽略了无效智能体引用：not-exists')
  })

  it('生成后保存：createPipelineTemplate 提交画布中的节点', async () => {
    vi.mocked(api.generatePipeline).mockResolvedValue(GENERATED_DRAFT as never)
    vi.mocked(api.createPipelineTemplate).mockResolvedValue({ ...TEMPLATES[0], id: 't-new', displayName: '发票自动审核流程' } as never)
    const wrapper = await mountPage()
    await wrapper.findAll('button').find(b => b.text().includes('AI 生成流程'))!.trigger('click')
    await wrapper.find('textarea.flow-requirement').setValue('员工报销单据自动审核，抽取发票字段并生成台账')
    await wrapper.findAll('button').find(b => b.text().includes('生成流程图'))!.trigger('click')
    await flushPromises()
    await wrapper.findAll('footer.dialog-foot button').find(b => b.text().includes('创建模板'))!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createPipelineTemplate)).toHaveBeenCalledWith(expect.objectContaining({
      name: 'invoice-audit-flow',
      displayName: '发票自动审核流程',
      nodes: expect.arrayContaining([expect.objectContaining({ nodeKey: 'extract', dependsOn: ['plan'] })]),
    }))
  })

  it('未配置模型网关（503）时展示明确错误而非假数据', async () => {
    vi.mocked(api.generatePipeline).mockRejectedValue(Object.assign(new Error('真实 Agent 需要配置 LLM_API_KEY'), { status: 503, code: 'LLM_NOT_CONFIGURED' }))
    const wrapper = await mountPage()
    await wrapper.findAll('button').find(b => b.text().includes('AI 生成流程'))!.trigger('click')
    await wrapper.find('textarea.flow-requirement').setValue('员工报销单据自动审核，抽取发票字段并生成台账')
    await wrapper.findAll('button').find(b => b.text().includes('生成流程图'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('真实 Agent 需要配置 LLM_API_KEY')
    expect(wrapper.text()).not.toContain('流程编排编辑器')
  })

  it('编辑现有模板：PUT 提交并保留节点', async () => {
    const template = { ...TEMPLATES[0], nodes: [{ nodeKey: 'n1', agentTypeId: 'a1', displayName: '规划', dependsOn: [], executionMode: 'sequential', config: {}, position: 0 }] }
    vi.mocked(api.pipelineTemplates).mockResolvedValue([template] as never)
    vi.mocked(api.updatePipelineTemplate).mockResolvedValue({ ...template, version: 2 } as never)
    const wrapper = await mountPage()
    await wrapper.find('button.button.subtle').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('编辑 · Web 全栈应用')
    expect(wrapper.text()).toContain('1 节点')
    await wrapper.findAll('footer.dialog-foot button').find(b => b.text().includes('保存修改'))!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.updatePipelineTemplate)).toHaveBeenCalledWith('t1', expect.objectContaining({ displayName: 'Web 全栈应用', nodes: expect.any(Array) }))
  })
})
