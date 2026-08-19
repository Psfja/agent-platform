import { createRouter, createWebHistory } from 'vue-router'
import { authTokens } from './api/client'
import ProjectsPage from './pages/ProjectsPage.vue'
import DashboardPage from './pages/DashboardPage.vue'
import TasksPage from './pages/TasksPage.vue'
import TaskDetailPage from './pages/TaskDetailPage.vue'
import IterationsPage from './pages/IterationsPage.vue'
import IterationDetailPage from './pages/IterationDetailPage.vue'
import ComparePage from './pages/ComparePage.vue'
import ArtifactsPage from './pages/ArtifactsPage.vue'
import RequirementsPage from './pages/RequirementsPage.vue'
import MembersPage from './pages/MembersPage.vue'
import CodePage from './pages/CodePage.vue'
import DocsPage from './pages/DocsPage.vue'
import DeploymentsPage from './pages/DeploymentsPage.vue'
import AgentRuntimePage from './pages/AgentRuntimePage.vue'
import AgentBuildPage from './pages/AgentBuildPage.vue'
import LoginPage from './pages/LoginPage.vue'
import AgentTypesPage from './pages/admin/AgentTypesPage.vue'
import AgentTypeEditPage from './pages/admin/AgentTypeEditPage.vue'
import SkillsPage from './pages/admin/SkillsPage.vue'
import PipelineTemplatesPage from './pages/admin/PipelineTemplatesPage.vue'
import SettingsPage from './pages/admin/SettingsPage.vue'
import UsersPage from './pages/admin/UsersPage.vue'
import ResourcesPage from './pages/admin/ResourcesPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/projects' },
    { path: '/login', component: LoginPage, meta: { title: '登录', layout: 'blank' } },
    { path: '/projects', component: ProjectsPage, meta: { title: '项目空间' } },
    { path: '/projects/:id', component: DashboardPage, meta: { title: '项目概览', project: true } },
    { path: '/projects/:id/requirements', component: RequirementsPage, meta: { title: '需求说明书', project: true } },
    { path: '/projects/:id/tasks', component: TasksPage, meta: { title: '任务执行', project: true } },
    { path: '/projects/:id/tasks/:taskId', component: TaskDetailPage, meta: { title: '任务详情', project: true } },
    { path: '/projects/:id/iterations', component: IterationsPage, meta: { title: '迭代历史', project: true } },
    { path: '/projects/:id/iterations/:iterId', component: IterationDetailPage, meta: { title: '迭代详情', project: true } },
    { path: '/projects/:id/compare', component: ComparePage, meta: { title: '版本对比', project: true } },
    { path: '/projects/:id/code', component: CodePage, meta: { title: '代码仓库', project: true } },
    { path: '/projects/:id/docs', component: DocsPage, meta: { title: '项目文档', project: true } },
    { path: '/projects/:id/deployments', component: DeploymentsPage, meta: { title: '部署中心', project: true } },
    { path: '/projects/:id/build', component: AgentBuildPage, meta: { title: 'AI 全栈构建', project: true } },
    { path: '/projects/:id/runtime', component: AgentRuntimePage, meta: { title: 'Agent 运行时', project: true } },
    { path: '/projects/:id/members', component: MembersPage, meta: { title: '成员与协作', project: true } },
    { path: '/projects/:id/artifacts', component: ArtifactsPage, meta: { title: '产物中心', project: true } },
    { path: '/admin/agent-types', component: AgentTypesPage, meta: { title: '智能体类型' } },
    { path: '/admin/agent-types/:id', component: AgentTypeEditPage, meta: { title: '智能体配置' } },
    { path: '/admin/skills', component: SkillsPage, meta: { title: 'Skill 管理与装配' } },
    { path: '/admin/pipeline-templates', component: PipelineTemplatesPage, meta: { title: '流程模板' } },
    { path: '/admin/resources', component: ResourcesPage, meta: { title: '资源监控' } },
    { path: '/admin/settings', component: SettingsPage, meta: { title: '系统设置' } },
    { path: '/admin/users', component: UsersPage, meta: { title: '用户与权限' } },
    { path: '/:pathMatch(.*)*', redirect: '/projects' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  if (to.meta.layout !== 'blank' && !authTokens.access()) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && authTokens.access()) return '/projects'
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '企业智能体平台')} · 智构`
})

export default router
