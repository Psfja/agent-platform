<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Bot, CheckCircle2, Clock3, Code2, ExternalLink, ListChecks, Pause, Play, Rocket, Sparkles } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api, type AgentBuildRecord, type ApplicationDeploymentRecord } from '../api/client'
import type { Project, Task } from '../types'
import ChangeRequestDialog from '../components/ChangeRequestDialog.vue'
import PageTitle from '../components/PageTitle.vue'
import ProgressRing from '../components/ProgressRing.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route = useRoute(); const router = useRouter(); const app = useAppStore()
const projectId = String(route.params.id)
const project = ref<Project|null>(null)
const tasks = ref<Task[]>([])
const builds = ref<AgentBuildRecord[]>([])
const deployments = ref<ApplicationDeploymentRecord[]>([])
const loading = ref(true); const errorMessage = ref(''); const showChange = ref(false); const busy = ref(false)

const latestBuild = computed(() => builds.value[0] || null)
const runningBuild = computed(() => builds.value.find(b => b.status === 'running' || b.status === 'waiting_approval') || null)
const latestDeployment = computed(() => deployments.value.find(d => d.status === 'running') || deployments.value[0] || null)
const doneTasks = computed(() => tasks.value.filter(t => t.status === 'completed').length)
const heroTitle = computed(() => {
  if (runningBuild.value) return runningBuild.value.status === 'waiting_approval' ? '等待人工审批' : `构建进行中 · ${runningBuild.value.currentStage || '准备中'}`
  if (latestDeployment.value && latestDeployment.value.status === 'running') return `已部署 · ${latestDeployment.value.version || 'latest'}`
  if (latestBuild.value?.status === 'completed') return '最近构建已完成'
  return '尚无构建记录'
})
const heroText = computed(() => {
  if (runningBuild.value) return runningBuild.value.status === 'waiting_approval' ? 'Agent 发起了敏感操作审批，请到 AI 全栈构建页面处理。' : 'DeepAgents 正在执行构建阶段，可在 AI 全栈构建页面实时查看。'
  if (latestDeployment.value && latestDeployment.value.status === 'running') return `${latestDeployment.value.backendContainer} / ${latestDeployment.value.frontendContainer} 正在运行。`
  if (latestBuild.value?.status === 'completed') return '通过「AI 全栈构建」发起新构建，或「提出新需求」触发增量迭代。'
  return '通过「AI 全栈构建」提交需求，由多智能体协作生成应用。'
})
const activeAgents = computed(() => [...new Set(tasks.value.filter(t => t.status === 'in_progress').map(t => t.agentShort || t.agent))])
async function load() {
  loading.value = true; errorMessage.value = ''
  try {
    const [p, t, b, d] = await Promise.all([api.project(projectId), api.tasks(projectId), api.agentBuilds(projectId).catch(() => []), api.applicationDeployments(projectId).catch(() => [])])
    project.value = p; tasks.value = t; builds.value = b; deployments.value = d
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法加载项目数据'
  } finally { loading.value = false }
}
async function togglePause() {
  if (!project.value) return
  busy.value = true
  try {
    const updated = await api.projectAction(projectId, project.value.status === 'paused' ? 'resume' : 'pause')
    project.value = updated
    app.toast(updated.status === 'paused' ? '项目已暂停' : '项目已继续', '项目状态已通过后端更新。')
  } catch (error) { app.toast('操作失败', error instanceof Error ? error.message : '请稍后重试') }
  finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <div class="content-width dashboard-page">
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else>
      <PageTitle :eyebrow="project?`项目 / ${project.template}`:'项目'" :title="project?.name||'加载中…'" :description="project?.description||''">
        <button class="button secondary" :disabled="busy||!project" @click="togglePause"><Play v-if="project?.status==='paused'" :size="16"/><Pause v-else :size="16"/>{{project?.status==='paused'?'继续执行':'暂停项目'}}</button>
        <button class="button primary" @click="showChange=true"><Sparkles :size="17"/>提出新需求</button>
      </PageTitle>

      <section class="project-hero-card">
        <div class="hero-progress"><ProgressRing :value="project?.progress||0" :size="82" :stroke="7"/><div><div class="hero-status-line"><StatusBadge v-if="project" :status="project.status"/><span>{{project?.version&&project.version!=='—'?`当前版本 ${project.version}`:'尚未构建'}}</span></div><h2>{{heroTitle}}</h2><p>{{heroText}}</p></div></div>
        <div v-if="runningBuild" class="hero-live"><span class="live-agent-avatar">AI<i></i></span><div><small>当前执行智能体</small><strong>{{runningBuild.currentStage||'构建中'}}</strong><span><Clock3 :size="13"/>进度 {{runningBuild.progress}}%</span></div><button class="button subtle" @click="router.push(`/projects/${projectId}/build`)">实时查看<ArrowRight :size="15"/></button></div>
        <div v-else-if="latestDeployment && latestDeployment.status==='running'" class="hero-live"><span class="live-agent-avatar">DO<i></i></span><div><small>当前部署</small><strong>{{latestDeployment.version||'latest'}} · {{latestDeployment.environment}}</strong><span><Clock3 :size="13"/>{{latestDeployment.hostPort?`端口 ${latestDeployment.hostPort}`:'容器运行中'}}</span></div><a class="button subtle" :href="latestDeployment.deployUrl" target="_blank" rel="noopener">访问应用<ExternalLink :size="14"/></a></div>
      </section>

      <div class="metric-grid">
        <article><span class="metric-icon indigo"><ListChecks :size="19"/></span><div><small>任务完成</small><strong>{{doneTasks}} <em>/ {{tasks.length}}</em></strong><span class="trend positive">真实任务数据</span></div></article>
        <article><span class="metric-icon green"><CheckCircle2 :size="19"/></span><div><small>成功构建</small><strong>{{builds.filter(b=>b.status==='completed').length}}<em> 次</em></strong><span class="trend positive">失败 {{builds.filter(b=>b.status==='failed').length}} 次</span></div></article>
        <article><span class="metric-icon blue"><Bot :size="19"/></span><div><small>活跃智能体</small><strong>{{activeAgents.length}} <em>/ {{new Set(tasks.map(t=>t.agentShort)).size}}</em></strong><span class="trend">{{tasks.filter(t=>t.status==='completed').length}} 个已完成</span></div></article>
        <article><span class="metric-icon amber"><Rocket :size="19"/></span><div><small>部署</small><strong>{{deployments.filter(d=>d.status==='running').length}}<em> 运行中</em></strong><span class="trend">{{deployments.length}} 条记录</span></div></article>
      </div>

      <div class="dashboard-columns">
        <section class="panel dashboard-tasks-card">
          <header class="panel-title"><div><h3>任务概览</h3><p>来自后端真实任务树</p></div><button class="text-button" @click="router.push(`/projects/${projectId}/tasks`)">查看任务树<ArrowRight :size="14"/></button></header>
          <div class="dashboard-task-list">
            <button v-for="task in tasks.slice(0,6)" :key="task.id" @click="router.push(`/projects/${projectId}/tasks/${task.id}`)"><StatusBadge :status="task.status"/><div><b>{{task.name}}</b><small>{{task.agent}}</small></div><span>{{task.duration}}</span></button>
            <div v-if="!tasks.length" class="deployment-empty-row">暂无任务 · 创建项目后由项目经理智能体自动规划</div>
          </div>
        </section>
        <section class="panel dashboard-builds-card">
          <header class="panel-title"><div><h3>构建与部署</h3><p>最近的 Agent Build 与部署记录</p></div><button class="text-button" @click="router.push(`/projects/${projectId}/build`)">AI 全栈构建<ArrowRight :size="14"/></button></header>
          <div class="dashboard-build-list">
            <button v-for="build in builds.slice(0,4)" :key="build.id" @click="router.push(`/projects/${projectId}/build`)"><span class="metric-icon indigo" style="width:31px;height:31px"><Code2 :size="15"/></span><div><b>{{build.mode==='incremental'?'增量':'初始'}}构建 · {{build.model}}</b><small>{{build.createdAt}}</small></div><StatusBadge :status="build.status"/></button>
            <button v-for="deployment in deployments.slice(0,2)" :key="deployment.id" @click="router.push(`/projects/${projectId}/deployments`)"><span class="metric-icon green" style="width:31px;height:31px"><Rocket :size="15"/></span><div><b>部署 {{deployment.version||''}} · {{deployment.environment}}</b><small>{{deployment.createdAt}}</small></div><StatusBadge :status="deployment.status"/></button>
            <div v-if="!builds.length&&!deployments.length" class="deployment-empty-row">暂无构建记录 · 在 AI 全栈构建页面发起首次构建</div>
          </div>
        </section>
      </div>
      <ChangeRequestDialog v-if="showChange" @close="showChange=false"/>
    </template>
  </div>
</template>
