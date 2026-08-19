<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, AlertTriangle, ArrowRight, Bot, Check, CheckCircle2, ChevronRight, Clock3, Code2, ExternalLink, FileCode2, GitBranch, ListChecks, MoreHorizontal, Pause, Play, Rocket, ShieldCheck, Sparkles, Users, Workflow, Zap } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
import { api } from '../api/client'
import { tasks } from '../data/mock'
import ChangeRequestDialog from '../components/ChangeRequestDialog.vue'
import PageTitle from '../components/PageTitle.vue'
import ProgressRing from '../components/ProgressRing.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route = useRoute(); const router = useRouter(); const app = useAppStore()
const project = computed(() => app.projects.find(p => p.id === route.params.id) || app.projects[0])
const showChange = ref(false); const paused = ref(false)
const activeTasks = computed(() => tasks.filter(t => t.status === 'in_progress'))
function togglePause(){ paused.value=!paused.value; app.toast(paused.value?'项目已暂停':'项目已继续', paused.value?'所有智能体将在当前工具调用完成后暂停。':'智能体执行队列已恢复。') }
</script>

<template>
  <div class="content-width dashboard-page">
    <PageTitle :eyebrow="`项目 / ${project.template}`" :title="project.name" :description="project.description">
      <button class="button secondary" @click="togglePause"><Play v-if="paused" :size="16"/><Pause v-else :size="16"/>{{ paused?'继续执行':'暂停项目' }}</button>
      <button class="button primary" @click="showChange=true"><Sparkles :size="17"/>提出新需求</button>
    </PageTitle>

    <section class="project-hero-card">
      <div class="hero-progress"><ProgressRing :value="project.progress" :size="82" :stroke="7"/><div><div class="hero-status-line"><StatusBadge :status="paused?'paused':project.status"/><span>增量迭代 · v1.3.0</span></div><h2>{{ paused ? '项目已暂停，等待继续执行' : '回归测试正在执行' }}</h2><p>{{ paused ? '任务上下文与执行状态已安全保存。' : '测试工程师正在验证 Excel 导出功能，并执行已有功能回归测试。' }}</p></div></div>
      <div class="hero-live"><span class="live-agent-avatar">QA<i></i></span><div><small>当前执行智能体</small><strong>测试工程师</strong><span><Clock3 :size="13"/>已运行 31 分钟</span></div><button class="button subtle" @click="router.push(`/projects/${project.id}/tasks/t-test`)">实时查看<ArrowRight :size="15"/></button></div>
    </section>

    <div class="metric-grid">
      <article><span class="metric-icon indigo"><ListChecks :size="19"/></span><div><small>任务完成</small><strong>18 <em>/ 25</em></strong><span class="trend positive">较昨日 +6</span></div></article>
      <article><span class="metric-icon green"><CheckCircle2 :size="19"/></span><div><small>测试通过率</small><strong>98.7<em>%</em></strong><span class="trend positive">+2.1%</span></div></article>
      <article><span class="metric-icon blue"><Bot :size="19"/></span><div><small>活跃智能体</small><strong>2 <em>/ 8</em></strong><span class="trend">6 个已完成</span></div></article>
      <article><span class="metric-icon amber"><Zap :size="19"/></span><div><small>Token 消耗</small><strong>142.6<em>k</em></strong><span class="trend">预算内 64%</span></div></article>
    </div>

    <div class="dashboard-grid">
      <section class="panel pipeline-panel">
        <header class="panel-title"><div><h3>执行流水线</h3><p>Web 全栈应用 · 增量模式</p></div><button class="text-button" @click="router.push(`/projects/${project.id}/tasks`)" >查看任务树<ArrowRight :size="15"/></button></header>
        <div class="pipeline-track">
          <div class="pipeline-stage done"><span><Check :size="15"/></span><b>影响分析</b><small>12m</small></div><i class="done"></i>
          <div class="pipeline-stage done"><span><Check :size="15"/></span><b>方案设计</b><small>18m</small></div><i class="done"></i>
          <div class="pipeline-stage done"><span><Check :size="15"/></span><b>增量开发</b><small>48m</small></div><i class="done"></i>
          <div class="pipeline-stage active"><span>4</span><b>回归测试</b><small>68%</small></div><i></i>
          <div class="pipeline-stage"><span>5</span><b>部署验证</b><small>待执行</small></div>
        </div>
        <div class="active-task-box">
          <div class="task-agent"><span>QA</span><i></i></div>
          <div class="task-active-copy"><span class="running-label"><i></i>正在运行</span><strong>回归测试与质量验证</strong><p>执行 128 项既有用例 + 24 项新增导出测试</p></div>
          <div class="active-progress"><span><b>104</b> / 152</span><div><i style="width:68%"></i></div><small>预计还需 14 分钟</small></div>
        </div>
      </section>

      <section class="panel health-panel">
        <header class="panel-title"><div><h3>项目健康度</h3><p>AI 每 5 分钟动态评估</p></div><button class="icon-button"><MoreHorizontal :size="18"/></button></header>
        <div class="health-score"><div class="gauge"><svg viewBox="0 0 120 68"><path d="M10 60 A50 50 0 0 1 110 60" pathLength="100"/><path class="gauge-value" d="M10 60 A50 50 0 0 1 110 60" pathLength="100"/></svg><strong>92</strong><small>健康</small></div></div>
        <div class="health-list"><div><span>进度健康</span><b class="green-text">良好</b></div><div><span>质量风险</span><b class="green-text">低</b></div><div><span>资源使用</span><b>正常</b></div></div>
        <div class="ai-insight"><Sparkles :size="16"/><p><b>AI 评估</b>当前进展顺利。建议关注大数据量导出场景的内存峰值，已加入测试范围。</p></div>
      </section>

      <section class="panel recent-tasks-panel">
        <header class="panel-title"><div><h3>最近任务</h3><p>智能体团队最新执行情况</p></div><button class="text-button" @click="router.push(`/projects/${project.id}/tasks`)" >全部任务<ArrowRight :size="15"/></button></header>
        <div class="recent-task-list">
          <button v-for="task in tasks.slice(2,7)" :key="task.id" @click="router.push(`/projects/${project.id}/tasks/${task.id}`)"><span class="agent-square">{{ task.agentShort }}</span><div><strong>{{ task.name }}</strong><small>{{ task.agent }} · {{ task.duration }}</small></div><StatusBadge :status="task.status"/><ChevronRight :size="16"/></button>
        </div>
      </section>

      <section class="panel activity-panel">
        <header class="panel-title"><div><h3>项目动态</h3><p>今天</p></div><button class="icon-button"><MoreHorizontal :size="18"/></button></header>
        <div class="activity-list">
          <div><span class="activity-dot green"><CheckCircle2 :size="14"/></span><p><b>代码审查通过</b><small>未发现阻塞项，记录 3 条优化建议</small></p><time>26 分钟前</time></div>
          <div><span class="activity-dot indigo"><GitBranch :size="14"/></span><p><b>合并增量代码</b><small>12 个文件，+684 / −57 行</small></p><time>42 分钟前</time></div>
          <div><span class="activity-dot blue"><Users :size="14"/></span><p><b>赵玮确认影响分析</b><small>启动 v1.3.0 增量迭代</small></p><time>2 小时前</time></div>
        </div>
      </section>
    </div>
    <ChangeRequestDialog v-if="showChange" @close="showChange=false"/>
  </div>
</template>
