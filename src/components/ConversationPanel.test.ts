import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api, ApiError } from '../api/client'
import ConversationPanel from './ConversationPanel.vue'

vi.mock('../api/client', () => ({
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
    agentTypes: vi.fn(),
    conversations: vi.fn(),
    createConversation: vi.fn(),
    conversation: vi.fn(),
    deleteConversation: vi.fn(),
    sendConversationMessage: vi.fn(),
    streamConversationMessage: vi.fn(),
    regenerateConversationTitle: vi.fn(),
    setConversationMode: vi.fn(),
    conversationInterrupts: vi.fn(),
    decideConversationInterrupt: vi.fn(),
    conversationWorkspace: vi.fn(),
  },
}))

const AGENTS = [
  { id: 'a1', name: 'project-manager', displayName: '项目经理', description: '', systemPrompt: 'p', model: 'm', tools: [], skills: [], sandboxConfig: {}, version: 1, isTemplate: true, isActive: true, createdAt: '', updatedAt: '' },
]
const CONVERSATION = { id: 'c1', projectId: 'leave-hub', agentKey: 'project-manager', mode: 'chat', title: '需求讨论', createdAt: '2026-08-20T08:00:00Z', updatedAt: '2026-08-20T09:00:00Z', lastMessageAt: '2026-08-20T09:00:00Z', messageCount: 2 }
const DETAIL = {
  ...CONVERSATION,
  messages: [
    { id: 'm1', role: 'user', content: '你好', metadata: {}, createdAt: '2026-08-20T08:00:00Z' },
    { id: 'm2', role: 'assistant', content: '你好，我是项目经理。', metadata: {}, createdAt: '2026-08-20T08:00:01Z' },
  ],
}
const STREAM_DONE = {
  conversation: { ...CONVERSATION, title: '导出功能规划', messageCount: 4 },
  assistantMessage: { id: 'm4', role: 'assistant' as const, content: '好的，我们分三步：字段抽取、异步导出、通知下载。', metadata: {}, createdAt: '2026-08-20T09:00:01Z' },
  memoriesUsed: [{ id: 'mem1', projectId: 'leave-hub', agentKey: 'project-manager', scope: 'project', memoryType: 'semantic', key: 'export-limit', content: '单次导出限制 5 万条', importance: 0.8, tags: [], metadata: {}, accessCount: 1, lastAccessedAt: null, expiresAt: null, createdAt: '', updatedAt: '' }],
  title: '导出功能规划',
}
const META = { historyMessages: 2, droppedMessages: 0, estimatedTokens: 640, budgetTokens: 6000, memoriesRecalled: 3, skillsLoaded: 2 }

async function mountPanel() {
  const wrapper = mount(ConversationPanel, { props: { projectId: 'leave-hub' }, global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('ConversationPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.agentTypes).mockResolvedValue(AGENTS as never)
    vi.mocked(api.conversations).mockResolvedValue([CONVERSATION] as never)
    vi.mocked(api.conversation).mockResolvedValue(DETAIL as never)
    vi.mocked(api.conversationInterrupts).mockResolvedValue([] as never)
    vi.mocked(api.conversationWorkspace).mockResolvedValue({ files: [] } as never)
  })

  it('加载会话列表并展示历史消息', async () => {
    const wrapper = await mountPanel()
    expect(wrapper.text()).toContain('需求讨论')
    expect(wrapper.text()).toContain('你好，我是项目经理。')
    expect(vi.mocked(api.conversation)).toHaveBeenCalledWith('leave-hub', 'c1')
  })

  it('流式发送：逐块拼接（打字机效果）→ 完成后替换为正式消息并展示上下文统计', async () => {
    vi.mocked(api.streamConversationMessage).mockImplementation(async (_p, _c, _content, _remember, handlers) => {
      handlers?.onMeta?.(META)
      handlers?.onDelta?.('好的，我们分三步：')
      handlers?.onDelta?.('字段抽取、异步导出、通知下载。')
      handlers?.onTitle?.('导出功能规划')
      return STREAM_DONE
    })
    const wrapper = await mountPanel()
    await wrapper.find('.conversation-input textarea').setValue('请规划导出功能')
    await wrapper.find('.conversation-input .button').trigger('click')
    // 流式期间：文本按块累积显示，且上下文统计已出现
    await flushPromises()
    expect(wrapper.text()).toContain('好的，我们分三步：字段抽取、异步导出、通知下载。')
    expect(wrapper.text()).toContain('召回记忆 3 条')
    expect(wrapper.text()).toContain('Tokens 640 / 6000')
    expect(wrapper.text()).toContain('export-limit')
    expect(vi.mocked(api.streamConversationMessage)).toHaveBeenCalledWith('leave-hub', 'c1', '请规划导出功能', true, expect.any(Object))
    // 标题由流式 title 事件更新
    expect(wrapper.text()).toContain('导出功能规划')
  })

  it('模型网关未配置（503）时给出明确提示而非模拟回复', async () => {
    vi.mocked(api.streamConversationMessage).mockRejectedValue(new ApiError(503, 'LLM_NOT_CONFIGURED', '真实对话需要配置 LLM_API_KEY'))
    const wrapper = await mountPanel()
    await wrapper.find('.conversation-input textarea').setValue('你好')
    await wrapper.find('.conversation-input .button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('真实对话需要配置 LLM_API_KEY')
    expect(wrapper.text()).toContain('不会返回模拟回复')
    expect(vi.mocked(api.sendConversationMessage)).not.toHaveBeenCalled()
  })

  it('流式不可用时降级为普通请求', async () => {
    vi.mocked(api.streamConversationMessage).mockRejectedValue(new TypeError('network down'))
    vi.mocked(api.sendConversationMessage).mockResolvedValue({
      conversation: { ...CONVERSATION, messageCount: 4 },
      userMessage: { id: 'm3', role: 'user', content: '请规划导出功能', metadata: {}, createdAt: '' },
      assistantMessage: STREAM_DONE.assistantMessage,
      memoriesUsed: [],
      context: META,
    } as never)
    const wrapper = await mountPanel()
    await wrapper.find('.conversation-input textarea').setValue('请规划导出功能')
    await wrapper.find('.conversation-input .button').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.sendConversationMessage)).toHaveBeenCalledWith('leave-hub', 'c1', '请规划导出功能', true)
    expect(wrapper.text()).toContain('好的，我们分三步')
  })

  it('点击魔法按钮调用 AI 重生成标题并更新', async () => {
    vi.mocked(api.regenerateConversationTitle).mockResolvedValue({ ...CONVERSATION, title: '发票审核讨论' } as never)
    const wrapper = await mountPanel()
    await wrapper.find('.title-wand').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.regenerateConversationTitle)).toHaveBeenCalledWith('leave-hub', 'c1')
    expect(wrapper.text()).toContain('发票审核讨论')
  })

  it('新建对话并切换', async () => {
    const created = { ...CONVERSATION, id: 'c2', title: '新对话', messageCount: 0 }
    vi.mocked(api.createConversation).mockResolvedValue(created as never)
    vi.mocked(api.conversation).mockResolvedValue({ ...created, messages: [] } as never)
    const wrapper = await mountPanel()
    await wrapper.find('.new-chat-button').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createConversation)).toHaveBeenCalledWith('leave-hub', 'project-manager')
    expect(wrapper.text()).toContain('开始和这个智能体对话吧')
  })

  it('切换工具模式调用 setConversationMode', async () => {
    vi.mocked(api.setConversationMode).mockResolvedValue({ ...CONVERSATION, mode: 'agent' } as never)
    const wrapper = await mountPanel()
    const buttons = wrapper.findAll('.mode-switch button')
    await buttons[1].trigger('click')
    await flushPromises()
    expect(vi.mocked(api.setConversationMode)).toHaveBeenCalledWith('leave-hub', 'c1', 'agent')
    // 工具模式按钮高亮
    expect(buttons[1].classes()).toContain('active')
  })

  it('流式中断后展示审批卡片，批准后插入恢复消息', async () => {
    vi.mocked(api.streamConversationMessage).mockImplementation(async (_p, _c, _content, _remember, handlers) => {
      handlers?.onDelta?.('我将执行部署操作。')
      handlers?.onInterrupt?.({ interruptId: 'int-1', toolName: 'request_production_deployment', payload: { version: 'v1.0', summary: '对话产物' } })
      return { ...STREAM_DONE, assistantMessage: null, interrupt: { toolName: 'request_production_deployment', payload: { version: 'v1.0' } } }
    })
    vi.mocked(api.decideConversationInterrupt).mockResolvedValue({
      conversation: { ...CONVERSATION, mode: 'agent', messageCount: 5 },
      assistantMessage: { id: 'm9', role: 'assistant', content: '已按审批意见完成部署。', metadata: {}, createdAt: '' },
    } as never)
    const wrapper = await mountPanel()
    await wrapper.find('.conversation-input textarea').setValue('请部署到生产')
    await wrapper.find('.conversation-input .button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('待人工审批')
    expect(wrapper.text()).toContain('request_production_deployment')
    // 批准
    await wrapper.findAll('.conversation-interrupt footer button').find(b => b.text().trim() === '批准')!.trigger('click')
    await flushPromises()
    expect(vi.mocked(api.decideConversationInterrupt)).toHaveBeenCalledWith('leave-hub', 'c1', 'int-1', 'approve', '', {})
    expect(wrapper.text()).toContain('已按审批意见完成部署。')
    expect(wrapper.text()).not.toContain('待人工审批')
  })

  it('删除会话并清空当前视图', async () => {
    vi.mocked(api.deleteConversation).mockResolvedValue(undefined)
    const wrapper = await mountPanel()
    await wrapper.find('.conversation-delete').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.deleteConversation)).toHaveBeenCalledWith('leave-hub', 'c1')
    expect(wrapper.text()).toContain('选择或新建一个对话')
  })
})
