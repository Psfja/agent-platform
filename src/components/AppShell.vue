<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Boxes, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Command, FileClock,
  FolderKanban, LayoutDashboard, BookOpen, Code2, Menu, Network, Search, Settings, Sparkles,
  Users, Workflow, X, Bell, CheckCircle2, AlertTriangle, Cpu, FileText, Rocket, BrainCircuit,
  Bot, Puzzle, Cable, PlusCircle, Info
} from 'lucide-vue-next'
import { api, type MonitoringSummary } from '../api/client'
import { useAppStore } from '../stores/app'

const app = useAppStore()
const route = useRoute()
const router = useRouter()
const profileOpen = ref(false)
const globalSearch = ref('')
const isProjectRoute = computed(() => Boolean(route.meta.project))
const projectId = computed(() => String(route.params.id || ''))
const project = computed(() => app.projects.find(p => p.id === projectId.value) || null)
const isAdmin = computed(() => app.currentUser?.platformRole === 'super_admin' || app.currentUser?.platformRole === 'platform_admin')
const userInitials = computed(() => app.currentUser?.displayName.slice(-2).toUpperCase() || '..')

const adminCounts = ref<{agents:number;skills:number}|null>(null)
const usage = ref<MonitoringSummary|null>(null)
const notices = ref<{id:string;eventType:string;title:string;content:string;status:string;readAt:string|null;createdAt:string}[]>([])
const unreadCount = computed(() => notices.value.filter(n => n.status === 'unread').length)
function fmtTokens(tokens:number):string{return tokens>=1_000_000?`${(tokens/1_000_000).toFixed(1)}M`:tokens>=1_000?`${(tokens/1_000).toFixed(1)}k`:String(tokens)}
async function loadAdminData(){
  if(!isAdmin.value)return
  try{
    const [agents,skills,monitoring]=await Promise.all([api.agentTypes(),api.skills(),api.monitoringSummary()])
    adminCounts.value={agents:agents.length,skills:skills.length}
    usage.value=monitoring
  }catch{adminCounts.value=null;usage.value=null}
}
async function loadNotifications(){
  try{notices.value=await api.notifications()}catch{notices.value=[]}
}
async function openNotice(item:{id:string;status:string}){
  if(item.status==='unread'){try{await api.readNotification(item.id);item.status='read'}catch{}}
}

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
onMounted(async()=>{await app.initAuth();await app.loadProjects();await loadAdminData();await loadNotifications()})
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
        <RouterLink to="/admin/agent-types" class="nav-item"><Bot :size="18"/><span>智能体管理</span><b v-if="adminCounts">{{adminCounts.agents}}</b></RouterLink>
        <RouterLink to="/admin/skills" class="nav-item"><Puzzle :size="18"/><span>Skill 管理与装配</span><b v-if="adminCounts">{{adminCounts.skills}}</b></RouterLink>
        <RouterLink to="/admin/pipeline-templates" class="nav-item"><Workflow :size="18"/><span>开发流程编排</span></RouterLink>

        <span class="nav-section">接入与平台</span>
        <RouterLink to="/admin/settings" class="nav-item"><Cable :size="18"/><span>模型与 API 配置</span></RouterLink>
        <RouterLink to="/admin/resources" class="nav-item"><Cpu :size="18"/><span>资源与运行监控</span></RouterLink>
        <RouterLink to="/admin/users" class="nav-item"><Users :size="18"/><span>用户与权限</span></RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div v-if="usage" class="usage-card">
          <div><span>平台运行</span><strong>{{usage.system.cpuPercent.toFixed(0)}}%</strong></div>
          <div class="usage-track"><i :style="{width:`${Math.min(100,usage.system.cpuPercent)}%`}"></i></div>
          <small>{{fmtTokens(usage.agentBuilds.tokens)}} Tokens 已消耗 · {{usage.projects.active}} 活跃项目</small>
        </div>
        <button class="nav-item" @click="app.toast('帮助与文档','帮助中心与文档站正在建设中，可先参考 README。')"><CircleHelp :size="18"/><span>帮助与文档</span></button>
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
          <button class="icon-button bell-button" @click="app.notificationsOpen = !app.notificationsOpen"><Bell :size="19"/><i v-if="unreadCount"></i></button>
          <div class="profile-wrap">
            <button class="profile-button" @click="profileOpen = !profileOpen"><span class="avatar">{{userInitials}}</span><div><strong>{{app.currentUser?.displayName||'…'}}</strong><small>{{app.currentUser?.platformRole||''}}</small></div><ChevronDown :size="15"/></button>
            <div v-if="profileOpen" class="profile-menu"><button @click="router.push('/admin/settings')">个人设置</button><button @click="app.toast('切换工作区','多工作区切换即将上线。')">切换工作区</button><button @click="app.logout()">退出登录</button></div>
          </div>
        </div>
        <div v-if="app.notificationsOpen" class="notification-panel">
          <div class="panel-head"><strong>通知</strong><button @click="app.notificationsOpen=false"><X :size="17"/></button></div>
          <button v-for="notice in notices.slice(0,20)" :key="notice.id" class="notification" :class="{unread:notice.status==='unread'}" @click="openNotice(notice)">
            <span class="notice-icon" :class="notice.eventType==='build_failed'||notice.eventType==='deployment_failed'?'amber':notice.status==='unread'?'blue':'green'"><AlertTriangle v-if="notice.eventType==='build_failed'||notice.eventType==='deployment_failed'" :size="16"/><CheckCircle2 v-else-if="notice.status==='read'" :size="16"/><Boxes v-else :size="16"/></span>
            <div><b>{{notice.title}}</b><p>{{notice.content}}</p><small>{{new Date(notice.createdAt).toLocaleString('zh-CN',{hour12:false})}}</small></div>
          </button>
          <div v-if="!notices.length" class="notification-empty"><Info :size="16"/><p>暂无站内通知</p></div>
        </div>
      </header>

      <div v-if="isProjectRoute" class="project-bar">
        <button class="back-projects" @click="router.push('/projects')"><ChevronLeft :size="16"/>项目空间</button>
        <span class="project-divider"></span>
        <div class="project-mini-icon"><FolderKanban :size="18"/></div>
        <div class="project-identity"><strong>{{ project?.name || '…' }}</strong><span>{{ project?.version }}</span></div>
        <nav class="project-tabs">
          <button v-for="tab in projectTabs" :key="tab.path" :class="{ active: isActive(tab.path) }" @click="goProject(tab.path)"><component :is="tab.icon" :size="16"/>{{ tab.label }}</button>
        </nav>
      </div>

      <main class="page-stage"><RouterView /></main>
    </section>
  </div>
</template>
