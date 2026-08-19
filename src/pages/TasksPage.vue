<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, ArrowRight, CheckCircle2, CircleDot, Clock3, Focus, Pause, Play, RefreshCcw, Workflow, ZoomIn, ZoomOut } from 'lucide-vue-next'
import { tasks as fallbackTasks } from '../data/mock'
import { api } from '../api/client'
import { useAppStore } from '../stores/app'
import type { Task } from '../types'
import PageTitle from '../components/PageTitle.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute(); const router=useRouter(); const app=useAppStore(); const projectId=String(route.params.id)
const taskItems=ref<Task[]>([...fallbackTasks])
const selected=ref<Task>(taskItems.value.find(t=>t.id==='t-test') || taskItems.value[0]); const showOnlyIncremental=ref(false); const scale=ref(1); const paused=ref(false)
const visibleTasks=computed(()=>showOnlyIncremental.value?taskItems.value.filter(t=>t.incremental):taskItems.value)
const stages=computed(()=>[
  {name:'规划',items:visibleTasks.value.filter(t=>['PM','RA','AR'].includes(t.agentShort))},
  {name:'增量开发',items:visibleTasks.value.filter(t=>['BE','FE','DB'].includes(t.agentShort))},
  {name:'质量保障',items:visibleTasks.value.filter(t=>['CR','QA'].includes(t.agentShort))},
  {name:'交付',items:visibleTasks.value.filter(t=>['DO'].includes(t.agentShort))},
].filter(s=>s.items.length))
const stats=computed(()=>({done:taskItems.value.filter(t=>t.status==='completed').length,running:taskItems.value.filter(t=>t.status==='in_progress').length,failed:taskItems.value.filter(t=>t.status==='failed').length,total:taskItems.value.length,progress:taskItems.value.length?Math.round(taskItems.value.reduce((sum,t)=>sum+t.progress,0)/taskItems.value.length):0}))
let events: EventSource | null = null
async function reload(showToast=false){
  try{const latest=await api.tasks(projectId);taskItems.value=latest;selected.value=latest.find(t=>t.id===selected.value?.id)||latest.find(t=>t.status==='in_progress')||latest[0];if(showToast)app.toast('状态已同步','任务树已更新到最新状态。')}catch{if(showToast)app.toast('刷新失败','无法连接后端，继续显示本地演示数据。')}
}
function pick(task:Task){selected.value=task}
function zoom(delta:number){scale.value=Math.min(1.2,Math.max(.8,scale.value+delta))}
async function toggle(){
  try{const project=await api.projectAction(projectId,paused.value?'resume':'pause');paused.value=project.status==='paused';app.replaceProject(project);await reload();app.toast(paused.value?'执行已暂停':'执行已继续',paused.value?'进行中的智能体将在安全点暂停。':'任务流水线已恢复。')}catch(error){app.toast('操作失败',error instanceof Error?error.message:'请稍后重试')}
}
onMounted(async()=>{await reload();events=api.connectEvents(projectId,()=>reload())})
onUnmounted(()=>events?.close())
</script>

<template>
  <div class="tasks-page">
    <div class="content-width task-page-head">
      <PageTitle title="任务执行" description="查看多智能体协作关系、任务状态和实时执行过程。">
        <button class="button secondary" @click="toggle"><Play v-if="paused" :size="16"/><Pause v-else :size="16"/>{{paused?'继续全部':'暂停全部'}}</button>
        <button class="button primary" @click="app.toast('状态已同步','任务树已更新到最新状态。')"><RefreshCcw :size="16"/>刷新状态</button>
      </PageTitle>
      <div class="task-summary-strip"><div><span class="pulse-dot"></span><strong>{{paused?'项目已暂停':'项目执行中'}}</strong><small>已连接实时事件</small></div><i></i><div><span>总体进度</span><b>{{stats.progress}}%</b></div><i></i><div><span>已完成</span><b>{{stats.done}}</b><small>/ {{stats.total}}</small></div><i></i><div><span>执行中</span><b class="indigo-text">{{stats.running}}</b></div><i></i><div><span>失败</span><b>{{stats.failed}}</b></div></div>
    </div>

    <div class="task-workspace">
      <section class="graph-area">
        <div class="graph-toolbar">
          <div class="graph-filter"><button class="active"><Workflow :size="15"/>任务树</button><button @click="app.toast('视图切换','列表视图将在完整版本提供。')">列表</button></div>
          <div class="graph-tools"><label class="switch-label"><input type="checkbox" v-model="showOnlyIncremental"/><i></i>仅看本次增量</label><span></span><button @click="zoom(-.1)"><ZoomOut :size="16"/></button><b>{{Math.round(scale*100)}}%</b><button @click="zoom(.1)"><ZoomIn :size="16"/></button><button @click="scale=1"><Focus :size="16"/>适应画布</button></div>
        </div>
        <div class="graph-canvas">
          <div class="graph-grid"></div>
          <div class="pipeline-graph" :style="{transform:`scale(${scale})`}">
            <template v-for="(stage,index) in stages" :key="stage.name">
              <div class="graph-stage">
                <span class="stage-label">{{stage.name}}</span>
                <button v-for="task in stage.items" :key="task.id" class="task-node" :class="[{selected:selected.id===task.id,incremental:task.incremental},`node-${task.status}`]" @click="pick(task)">
                  <span class="node-agent">{{task.agentShort}}<i v-if="task.status==='in_progress'"></i></span>
                  <div><strong>{{task.name}}</strong><small>{{task.agent}}</small><div class="node-meta"><StatusBadge :status="task.status"/><span>{{task.duration}}</span></div><div v-if="task.status==='in_progress'" class="node-progress"><i :style="{width:`${task.progress}%`}"></i></div></div>
                  <em v-if="task.incremental">增量</em>
                </button>
              </div>
              <div v-if="index<stages.length-1" class="graph-connector"><i></i><ArrowRight :size="17"/></div>
            </template>
          </div>
          <div class="graph-legend"><span><i class="legend-done"></i>已完成</span><span><i class="legend-running"></i>执行中</span><span><i class="legend-pending"></i>待执行</span><span><i class="legend-incremental"></i>增量任务</span></div>
        </div>
      </section>

      <aside class="task-inspector">
        <div class="inspector-head"><span class="large-agent">{{selected.agentShort}}<i v-if="selected.status==='in_progress'"></i></span><div><StatusBadge :status="selected.status"/><h3>{{selected.name}}</h3><p>{{selected.agent}}</p></div></div>
        <div v-if="selected.status==='in_progress'" class="inspector-progress"><div><span>执行进度</span><b>{{selected.progress}}%</b></div><div><i :style="{width:`${selected.progress}%`}"></i></div><small><Clock3 :size="13"/>预计还需 14 分钟</small></div>
        <p class="task-description">{{selected.description}}</p>
        <dl class="task-facts"><div><dt>开始时间</dt><dd>{{selected.startedAt}}</dd></div><div><dt>已运行</dt><dd>{{selected.duration}}</dd></div><div><dt>Token 消耗</dt><dd>{{selected.tokens || '—'}}</dd></div><div><dt>涉及文件</dt><dd>{{selected.files ?? '—'}}</dd></div></dl>
        <div class="current-action" v-if="selected.status==='in_progress'"><div><Activity :size="15"/><span>当前操作</span><i></i></div><p>执行 E2E：筛选假勤记录 → 发起导出 → 查询进度 → 下载文件</p><small>tool.shell · pytest</small></div>
        <div class="inspector-section"><h4>依赖关系</h4><div class="dependency"><span class="dep done"><CheckCircle2 :size="14"/></span><div><b>增量代码审查</b><small>上游 · 已完成</small></div></div><div class="dependency"><span class="dep pending"><CircleDot :size="14"/></span><div><b>构建镜像并部署</b><small>下游 · 等待当前任务</small></div></div></div>
        <button class="button primary full" @click="router.push(`/projects/${projectId}/tasks/${selected.id}`)">查看完整执行过程<ArrowRight :size="16"/></button>
      </aside>
    </div>
  </div>
</template>
