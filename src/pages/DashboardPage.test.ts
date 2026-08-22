import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../api/client'
import DashboardPage from './DashboardPage.vue'

const { routeState, routerPush } = vi.hoisted(() => ({
  routeState: { params: { id: 'leave-hub' } as Record<string, string> },
  routerPush: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => routeState, useRouter: () => ({ push: routerPush }) }))
vi.mock('../api/client', () => ({
  api: {
    project: vi.fn(),
    tasks: vi.fn(),
    agentBuilds: vi.fn(),
    applicationDeployments: vi.fn(),
    projectAction: vi.fn(),
  },
}))
vi.mock('../components/ChangeRequestDialog.vue', () => ({ default: { template: '<div class="change-dialog-stub"/>' } }))

const PROJECT = { id: 'leave-hub', name: '员工假勤管理平台', description: '一体化内部应用。', status: 'executing' as const, progress: 64, version: 'v1.2.0', template: 'Web 全栈应用', owner: '林嘉', updatedAt: '1 小时前', members: ['LJ'], tasks: { done: 4, total: 7 }, risk: 'low' as const }
const TASKS = [
  { id: 't1', parentId: null, name: '需求解析', agent: '需求分析智能体', agentShort: 'RA', status: 'completed', progress: 100, duration: '12m', startedAt: '今天 09:32', description: 'd' },
  { id: 't2', parentId: null, name: '回归测试', agent: '测试工程师智能体', agentShort: 'QA', status: 'in_progress', progress: 40, duration: '31m', startedAt: '今天 11:22', description: 'd' },
]
const BUILDS = [{ id: 'b1', projectId: 'leave-hub', iterationId: null, requirement: 'r', template: 'fullstack', mode: 'incremental', baseBuildId: null, model: 'deepseek-chat', status: 'running', currentStage: 'testing', progress: 70, plan: {}, generatedFiles: [], changedFilesCount: 0, coverage: null, testResults: [], attempt: 0, maxFixAttempts: 5, promptTokens: 0, completionTokens: 0, workspacePath: '', artifactPath: '', errorMessage: '', cancellationRequested: false, startedAt: null, finishedAt: null, createdAt: '2026-08-20T10:00:00Z', updatedAt: '2026-08-20T10:00:00Z', logs: [] }]

async function mountPage() {
  const wrapper = mount(DashboardPage, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('DashboardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerPush.mockClear()
    vi.mocked(api.project).mockResolvedValue(PROJECT)
    vi.mocked(api.tasks).mockResolvedValue(TASKS as never)
    vi.mocked(api.agentBuilds).mockResolvedValue(BUILDS as never)
    vi.mocked(api.applicationDeployments).mockResolvedValue([] as never)
  })

  it('渲染真实项目、任务与构建指标', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('员工假勤管理平台')
    expect(wrapper.text()).toContain('需求解析')
    expect(wrapper.text()).toContain('回归测试')
    expect(wrapper.text()).toContain('构建进行中 · testing') // 运行中构建的阶段
    const metrics = wrapper.findAll('.metric-grid article')
    expect(metrics[0].find('strong').text()).toContain('1') // 完成任务数
    expect(metrics[2].find('strong').text()).toContain('1') // 活跃智能体
  })

  it('暂停/继续调用真实 projectAction', async () => {
    vi.mocked(api.projectAction).mockResolvedValue({ ...PROJECT, status: 'paused' })
    const wrapper = await mountPage()
    await wrapper.find('.page-actions button.button.secondary').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.projectAction)).toHaveBeenCalledWith('leave-hub', 'pause')
  })

  it('无构建记录时展示引导', async () => {
    vi.mocked(api.agentBuilds).mockResolvedValue([] as never)
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('尚无构建记录')
  })

  it('加载失败时展示错误并可重试', async () => {
    vi.mocked(api.project).mockRejectedValueOnce(new Error('项目不存在'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('项目不存在')
  })
})
