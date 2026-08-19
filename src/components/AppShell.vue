<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Boxes, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Command, FileClock,
  FolderKanban, LayoutDashboard, BookOpen, Code2, Menu, Network, Search, Settings, Sparkles,
  Users, Workflow, X, Bell, CheckCircle2, AlertTriangle, Cpu, FileText, Rocket, BrainCircuit,
  Bot, Puzzle, Cable, PlusCircle
} from 'lucide-vue-next'
import { useAppStore } from '../stores/app'

const app = useAppStore()
const route = useRoute()
const router = useRouter()
const profileOpen = ref(false)
const globalSearch = ref('')
const isProjectRoute = computed(() => Boolean(route.meta.project))
const projectId = computed(() => String(route.params.id || 'leave-hub'))
const project = computed(() => app.projects.find(p => p.id === projectId.value) || app.projects[0])
const userInitials = computed(() => app.currentUser?.displayName.slice(-2).toUpperCase() || 'LJ')

const projectTabs = computed(() => [
  { label: '概览', icon: LayoutDashboard, path: `/projects/${projectId.value}` },
  { label: '需求', icon: FileText, path: `/projects/${projectId.value}/requirements` },
  { label: '任务', icon: Workflow, path: `/projects/${projectId.value}/tasks` },
  { label: '迭代', icon: FileClock, path: `/projects/${projectId.value}/iterations` },
  { label: '代码', icon: Code2, path: `/projects/${projectId.value}/code` },
  { label: '文档', icon: BookOpen, path: `/projects/${projectId.value}/docs` },
  { label: '构建', icon: Sparkles, path: `/projects/${projectId.value}/build` },
  { label: '部署', icon: Rocket, path: `/projects/${projectId.value}/deployments` },
  { label: 'Agent', icon: BrainCircuit, path: `/projects/${projectId.value}/runtime` },
  { label: '成员', icon: Users, path: `/projects/${projectId.value}/members` },
])

function isActive(path: string) {
  if (path === `/projects/${projectId.value}`) return route.path === path
  return route.path.startsWith(path)
}
function goProject(path: string) { router.push(path) }
onMounted(async()=>{await app.initAuth();await app.loadProjects()})
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-mini': app.sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand" @click="router.push('/projects')">
        <span class="brand-mark"><Command :size="19" :stroke-width="2.4" /></span>
        <div class="brand-copy"><strong>智构</strong><small>AGENT STUDIO</small></div>
      </div>

      <nav class="main-nav">
        <span class="nav-section">工作空间</span>
        <RouterLink to="/projects" class="nav-item"><FolderKanban :size="18"/><span>项目空间</span><b>{{app.projects.length}}</b></RouterLink>

        <span class="nav-section">智能体工坊</span>
        <RouterLink to="/admin/agent-types/new" class="nav-item"><PlusCircle :size="18"/><span>创建智能体</span></RouterLink>
        <RouterLink to="/admin/agent-types" class="nav-item"><Bot :size="18"/><span>智能体管理</span><b>7</b></RouterLink>
        <RouterLink to="/admin/skills" class="nav-item"><Puzzle :size="18"/><span>Skill 管理与装配</span><b>3</b></RouterLink>
        <RouterLink to="/admin/pipeline-templates" class="nav-item"><Workflow :size="18"/><span>开发流程编排</span></RouterLink>

        <span class="nav-section">接入与平台</span>
        <RouterLink to="/admin/settings" class="nav-item"><Cable :size="18"/><span>模型与 API 配置</span></RouterLink>
        <RouterLink to="/admin/resources" class="nav-item"><Cpu :size="18"/><span>资源与运行监控</span></RouterLink>
        <RouterLink to="/admin/users" class="nav-item"><Users :size="18"/><span>用户与权限</span></RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="usage-card">
          <div><span>本月算力</span><strong>68%</strong></div>
          <div class="usage-track"><i></i></div>
          <small>42.8M / 63M Tokens</small>
        </div>
        <button class="nav-item"><CircleHelp :size="18"/><span>帮助与文档</span></button>
        <button class="collapse-btn" @click="app.sidebarCollapsed = !app.sidebarCollapsed">
          <ChevronLeft v-if="!app.sidebarCollapsed" :size="16"/><ChevronRight v-else :size="16"/>
          <span>收起导航</span>
        </button>
      </div>
    </aside>

    <section class="app-main">
      <header class="topbar">
        <button class="mobile-menu icon-button" @click="app.sidebarCollapsed = !app.sidebarCollapsed"><Menu :size="19"/></button>
        <div class="search-box">
          <Search :size="17"/><input v-model="globalSearch" placeholder="搜索项目、任务或产物…"/><kbd>⌘ K</kbd>
        </div>
        <div class="top-actions">
          <button class="icon-button bell-button" @click="app.notificationsOpen = !app.notificationsOpen"><Bell :size="19"/><i></i></button>
          <div class="profile-wrap">
            <button class="profile-button" @click="profileOpen = !profileOpen"><span class="avatar">{{userInitials}}</span><div><strong>{{app.currentUser?.displayName||'林嘉'}}</strong><small>{{app.currentUser?.platformRole||'项目成员'}}</small></div><ChevronDown :size="15"/></button>
            <div v-if="profileOpen" class="profile-menu"><button @click="router.push('/admin/settings')">个人设置</button><button>切换工作区</button><button @click="app.logout()">退出登录</button></div>
          </div>
        </div>
        <div v-if="app.notificationsOpen" class="notification-panel">
          <div class="panel-head"><strong>通知</strong><button @click="app.notificationsOpen=false"><X :size="17"/></button></div>
          <div class="notification unread"><span class="notice-icon amber"><AlertTriangle :size="16"/></span><div><b>回归测试需要关注</b><p>文件名时区断言已自动重试通过。</p><small>3 分钟前</small></div></div>
          <div class="notification unread"><span class="notice-icon green"><CheckCircle2 :size="16"/></span><div><b>代码审查已通过</b><p>增量版本 v1.3.0 未发现阻塞问题。</p><small>26 分钟前</small></div></div>
          <div class="notification"><span class="notice-icon blue"><Boxes :size="16"/></span><div><b>镜像构建完成</b><p>供应商风险评估系统 rc.2 已就绪。</p><small>1 小时前</small></div></div>
        </div>
      </header>

      <div v-if="isProjectRoute" class="project-bar">
        <button class="back-projects" @click="router.push('/projects')"><ChevronLeft :size="16"/>项目空间</button>
        <span class="project-divider"></span>
        <div class="project-mini-icon"><FolderKanban :size="18"/></div>
        <div class="project-identity"><strong>{{ project.name }}</strong><span>{{ project.version }}</span></div>
        <nav class="project-tabs">
          <button v-for="tab in projectTabs" :key="tab.path" :class="{ active: isActive(tab.path) }" @click="goProject(tab.path)"><component :is="tab.icon" :size="16"/>{{ tab.label }}</button>
        </nav>
      </div>

      <main class="page-stage"><RouterView /></main>
    </section>
  </div>
</template>
