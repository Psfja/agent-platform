<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, CalendarDays, CheckCircle2, Clock3, FolderKanban, MoreHorizontal, Plus, Search, Sparkles, Users, Workflow } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import NewProjectDialog from '../components/NewProjectDialog.vue'
import PageTitle from '../components/PageTitle.vue'
import ProgressRing from '../components/ProgressRing.vue'
import StatusBadge from '../components/StatusBadge.vue'

const app = useAppStore()
const router = useRouter()
const search = ref('')
const filter = ref('all')
const showCreate = ref(false)
const filtered = computed(() => app.projects.filter(p => {
  const matchSearch = `${p.name}${p.description}`.toLowerCase().includes(search.value.toLowerCase())
  const matchFilter = filter.value === 'all' || (filter.value === 'active' ? ['executing','testing'].includes(p.status) : p.status === filter.value)
  return matchSearch && matchFilter
}))
const stats = computed(() => ({ active: app.projects.filter(p => ['executing','testing'].includes(p.status)).length, done: app.projects.filter(p => p.status === 'completed').length }))
function statusColor(status: string) { return status === 'completed' ? '#12a675' : status === 'testing' ? '#e79b2f' : status === 'draft' ? '#94a0b4' : '#6255d9' }
</script>

<template>
  <div class="content-width projects-page">
    <PageTitle title="项目空间" description="管理由智能体团队构建的应用，持续追踪交付与演进。">
      <button class="button primary" @click="showCreate=true"><Plus :size="17"/>创建项目</button>
    </PageTitle>

    <section class="workspace-summary">
      <div class="summary-copy"><span class="summary-icon"><Sparkles :size="21"/></span><div><strong>{{ app.currentUser?.displayName ? `你好，${app.currentUser.displayName}` : '项目空间' }}</strong><p>{{ stats.active }} 个项目正在执行{{ stats.done ? `，${stats.done} 个已交付` : '' }}。</p></div></div>
      <div class="summary-stats"><div><span class="dot indigo"></span><strong>{{ stats.active }}</strong><small>进行中</small></div><i></i><div><span class="dot green"></span><strong>{{ stats.done }}</strong><small>已交付</small></div><i></i><div><span class="dot amber"></span><strong>{{ app.projects.filter(p=>p.status==='draft').length }}</strong><small>草稿</small></div></div>
    </section>

    <div class="list-toolbar">
      <div class="segmented"><button :class="{active:filter==='all'}" @click="filter='all'">全部 <span>{{ app.projects.length }}</span></button><button :class="{active:filter==='active'}" @click="filter='active'">进行中</button><button :class="{active:filter==='completed'}" @click="filter='completed'">已完成</button><button :class="{active:filter==='draft'}" @click="filter='draft'">草稿</button></div>
      <div class="inline-search"><Search :size="16"/><input v-model="search" placeholder="搜索项目"/></div>
    </div>

    <div v-if="app.projectsLoading && !app.projects.length" class="project-grid">
      <article v-for="n in 6" :key="n" class="project-card skeleton-card">
        <header><span class="skeleton skeleton-avatar" style="width:44px;height:44px;border-radius:12px"></span><div style="flex:1"><div class="skeleton skeleton-cell" style="width:60%;height:15px"></div><div class="skeleton skeleton-cell" style="width:36%;height:11px"></div></div></header>
        <div class="skeleton skeleton-cell" style="width:92%"></div>
        <div class="skeleton skeleton-cell" style="width:70%"></div>
        <footer style="display:flex;gap:14px"><span class="skeleton skeleton-chip" style="width:56px"></span><span class="skeleton skeleton-chip" style="width:56px"></span><span class="skeleton skeleton-chip" style="width:44px"></span></footer>
      </article>
    </div>
    <div v-else-if="filtered.length" class="project-grid">
      <article v-for="project in filtered" :key="project.id" class="project-card" @click="router.push(`/projects/${project.id}`)">
        <header>
          <span class="project-icon" :class="`project-icon-${project.status}`"><FolderKanban :size="22"/></span>
          <div class="project-name"><h3>{{ project.name }}</h3><span>{{ project.template }}</span></div>
          <button class="icon-button" @click.stop="app.toast('项目操作', '更多项目操作菜单已打开。')"><MoreHorizontal :size="19"/></button>
        </header>
        <p class="project-desc">{{ project.description }}</p>
        <div class="project-meta-row"><StatusBadge :status="project.status"/><span><CalendarDays :size="14"/>{{ project.updatedAt }}更新</span></div>
        <div class="project-progress">
          <ProgressRing :value="project.progress" :size="58" :stroke="5" :color="statusColor(project.status)"/>
          <div><span>任务进度</span><strong>{{ project.tasks.done }} / {{ project.tasks.total }} <small>项任务</small></strong><div class="mini-track"><i :style="{width:`${project.progress}%`, background:statusColor(project.status)}"></i></div></div>
        </div>
        <footer>
          <div class="avatar-group"><span v-for="member in project.members.slice(0,4)" :key="member">{{ member }}</span><small>{{ project.members.length }} 位成员</small></div>
          <div class="card-version"><span>{{ project.version }}</span><ArrowRight :size="16"/></div>
        </footer>
      </article>
      <button class="create-card" @click="showCreate=true"><span><Plus :size="23"/></span><strong>创建新项目</strong><p>用自然语言描述需求<br/>让智能体团队完成交付</p></button>
    </div>
    <div v-else class="empty-state"><span><FolderKanban :size="26"/></span><h3>没有找到匹配的项目</h3><p>尝试更换搜索词或筛选条件。</p><button class="button secondary" @click="search='';filter='all'">清除筛选</button></div>

    <NewProjectDialog v-if="showCreate" @close="showCreate=false"/>
  </div>
</template>
