<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowLeft, Check, ChevronRight, Clock3, Code2, Database, FileCode2, GitCompareArrows, GitBranch, ListChecks, Rocket, ShieldCheck, UserRound } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import type { Iteration, Task } from '../types'
import { useAppStore } from '../stores/app'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const router=useRouter();const app=useAppStore()
const projectId=String(route.params.id);const iterationId=String(route.params.iterId)
const iteration=ref<Iteration|null>(null);const tasks=ref<Task[]>([]);const previous=ref<Iteration|null>(null)
const loading=ref(false);const errorMessage=ref('');const tab=ref('overview')
const impact=computed(()=>iteration.value?.impactAnalysis as Record<string,any>|null|undefined)
const iterationTasks=computed(()=>tasks.value.filter(t=>t.iterationId===iterationId))
const riskLabel=computed(()=>impact.value?.riskLevel==='high'?'高风险':impact.value?.riskLevel==='medium'?'中风险':'低风险')
async function load(){
  loading.value=true;errorMessage.value=''
  try{
    const [it,t,list]=await Promise.all([api.iteration(projectId,iterationId),api.tasks(projectId),api.iterations(projectId)])
    iteration.value=it;tasks.value=t
    const index=list.findIndex(item=>item.id===iterationId)
    previous.value=index>=0&&index+1<list.length?list[index+1]:null
  }catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载迭代详情'}
  finally{loading.value=false}
}
onMounted(load)
</script>

<template>
  <div class="content-width iteration-detail-page">
    <button class="back-link" @click="router.push(`/projects/${projectId}/iterations`)"><ArrowLeft :size="16"/>返回迭代历史</button>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else-if="iteration">
      <section class="iteration-detail-hero">
        <div>
          <span class="version-badge" :class="`type-${iteration.type}`"><GitBranch :size="16"/>{{iteration.version}}</span>
          <StatusBadge :status="iteration.status"/>
          <h1>{{iteration.title}}</h1>
          <p>{{iteration.description}}</p>
          <div><span><UserRound :size="14"/>{{iteration.author}} 提出</span><span><Clock3 :size="14"/>{{iteration.date}}</span></div>
        </div>
        <div class="iteration-hero-stats">
          <div><small>变更文件</small><strong>{{iteration.files}}</strong></div>
          <div><small>代码变化</small><strong class="green-text">+{{iteration.added}}</strong><em>−{{iteration.removed}}</em></div>
          <div><small>测试通过</small><strong>{{iteration.tests}}%</strong></div>
        </div>
      </section>
      <div class="iteration-detail-tabs">
        <button v-for="item in [['overview','迭代概览'],['tasks','关联任务'],['changes','影响分析']]" :key="item[0]" :class="{active:tab===item[0]}" @click="tab=item[0]">{{item[1]}}</button>
      </div>
      <section v-if="tab==='overview'" class="iteration-overview-grid">
        <div>
          <article class="panel change-request-card"><header class="panel-title"><div><h3>变更需求</h3><p>CHANGE REQUEST</p></div></header><blockquote>{{iteration.description}}</blockquote><footer><span class="member-avatar">{{iteration.author.slice(0,2).toUpperCase()}}</span><div><b>{{iteration.author}}</b><small>项目成员</small></div><span>{{iteration.date}}</span></footer></article>
          <article v-if="impact" class="panel impact-detail-card">
            <header class="panel-title"><div><h3>变更影响分析</h3><p>由项目经理智能体生成</p></div><span class="risk-low" :style="impact.riskLevel==='high'?'color:var(--red);background:var(--red-soft)':''"><ShieldCheck :size="15"/>{{riskLabel}}</span></header>
            <div class="impact-detail-metrics">
              <div><span class="metric-icon indigo"><FileCode2 :size="18"/></span><p><small>影响模块</small><strong>{{impact.modules?.length||0}} 个</strong></p></div>
              <div><span class="metric-icon blue"><Code2 :size="18"/></span><p><small>预计文件</small><strong>{{impact.estimatedFiles?.min||'—'}}–{{impact.estimatedFiles?.max||'—'}} 个</strong></p></div>
              <div><span class="metric-icon green"><Database :size="18"/></span><p><small>数据库变更</small><strong>{{impact.databaseChange?'是':'无'}}</strong></p></div>
            </div>
            <div class="affected-modules">
              <div v-for="(mod,index) in (impact.modules||[])" :key="index"><span>{{mod.name}}</span><b>{{mod.change}}</b></div>
            </div>
            <div v-if="impact.recommendations?.length" class="warning-box"><ShieldCheck :size="17"/><div><b>分析建议</b><span>{{impact.recommendations.join('；')}}</span></div></div>
          </article>
        </div>
        <aside>
          <section class="panel iteration-progress-card">
            <header class="panel-title"><div><h3>执行状态</h3><p>{{iterationTasks.length}} 个关联任务</p></div><strong>{{iteration.deployStatus}}</strong></header>
            <div class="vertical-stage-list">
              <div v-for="task in iterationTasks.slice(0,5)" :key="task.id" :class="{done:task.status==='completed',active:task.status==='in_progress'}">
                <span><Check v-if="task.status==='completed'" :size="14"/><b v-else>{{iterationTasks.indexOf(task)+1}}</b></span>
                <p><b>{{task.name}}</b><small>{{task.agent}} · {{task.duration}}</small></p>
              </div>
              <div v-if="!iterationTasks.length"><p><small>该迭代暂无关联任务记录</small></p></div>
            </div>
          </section>
          <section class="panel iteration-links">
            <h3>相关链接</h3>
            <button v-if="previous" @click="router.push(`/projects/${projectId}/compare?from=${encodeURIComponent(previous.version)}&to=${encodeURIComponent(iteration.version)}`)"><GitCompareArrows :size="16"/>与 {{previous.version}} 对比<ChevronRight :size="15"/></button>
            <button @click="router.push(`/projects/${projectId}/tasks`)"><ListChecks :size="16"/>查看任务树<ChevronRight :size="15"/></button>
            <button @click="router.push(`/projects/${projectId}/deployments`)"><Rocket :size="16"/>部署中心<ChevronRight :size="15"/></button>
          </section>
        </aside>
      </section>
      <section v-else-if="tab==='tasks'" class="panel iteration-tab-panel">
        <header class="panel-title"><div><h3>本次迭代任务</h3><p>来自真实任务树（按迭代关联）</p></div></header>
        <div class="iteration-task-table">
          <div v-for="(task,index) in iterationTasks" :key="task.id"><span class="task-order">{{String(index+1).padStart(2,'0')}}</span><span class="agent-square">{{task.agentShort}}</span><p><b>{{task.name}}</b><small>{{task.agent}} · {{task.description}}</small></p><StatusBadge :status="task.status"/><span>{{task.duration}}</span><button class="text-button" @click="router.push(`/projects/${projectId}/tasks/${task.id}`)">查看日志<ChevronRight :size="14"/></button></div>
          <div v-if="!iterationTasks.length" class="deployment-empty-row">该迭代暂无关联任务</div>
        </div>
      </section>
      <section v-else class="panel iteration-tab-panel">
        <header class="panel-title"><div><h3>影响分析详情</h3><p>变更类型、API 影响与建议智能体</p></div></header>
        <div v-if="impact" class="impact-detail-metrics" style="padding:13px 16px">
          <div><span class="metric-icon indigo"><FileCode2 :size="18"/></span><p><small>变更类型</small><strong>{{impact.changeType||'—'}}</strong></p></div>
          <div><span class="metric-icon blue"><Code2 :size="18"/></span><p><small>API 影响</small><strong>{{impact.existingApiImpact?'是':'无'}}</strong></p></div>
          <div><span class="metric-icon amber"><ListChecks :size="18"/></span><p><small>建议智能体</small><strong>{{impact.suggestedAgents?.length||0}} 个</strong></p></div>
        </div>
        <div v-if="impact?.breakingChanges?.length" class="warning-box" style="margin:12px 16px 16px"><ShieldCheck :size="17"/><div><b>破坏性变更</b><span>{{impact.breakingChanges.join('；')}}</span></div></div>
        <div v-else class="deployment-empty-row">暂无影响分析数据（由「提出新需求」流程生成）</div>
      </section>
    </template>
    <div v-else-if="!loading" class="admin-empty"><p>未找到该迭代</p></div>
  </div>
</template>
