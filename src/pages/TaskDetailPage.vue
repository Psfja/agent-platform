<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, ArrowLeft, Bot, Check, Clock3, LoaderCircle, Pause, Play, Send, XCircle } from 'lucide-vue-next'
import { api, type InterventionRecord, type TaskLogRecord } from '../api/client'
import { useAppStore } from '../stores/app'
import StatusBadge from '../components/StatusBadge.vue'
import type { Task } from '../types'

const route=useRoute();const router=useRouter();const app=useAppStore()
const projectId=String(route.params.id);const taskId=String(route.params.taskId)
const taskData=ref<Task|null>(null);const loading=ref(true);const errorMessage=ref('')
const logs=ref<TaskLogRecord[]>([]);const tab=ref('logs');const paused=ref(false);const intervention=ref('');const logFilter=ref('全部日志');const busy=ref(false)
const interventions=ref<{time:string;text:string;status:string}[]>([])
const task=computed(()=>taskData.value)
const filteredLogs=computed(()=>logs.value.filter(item=>logFilter.value==='全部日志'||item.type===logFilter.value))
function formatLogTime(value:string){return value.includes('T')?new Date(value).toLocaleTimeString('zh-CN',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}):value}
async function load(){
  loading.value=true;errorMessage.value=''
  try{
    const [latest,latestLogs,history]=await Promise.all([api.task(projectId,taskId),api.logs(projectId,taskId),api.interventions(projectId,taskId)])
    taskData.value=latest;paused.value=latest.status==='paused';logs.value=latestLogs
    interventions.value=history.map(item=>({time:new Date(item.createdAt).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}),text:item.content,status:item.agentResponse||item.status}))
  }catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载任务详情'}
  finally{loading.value=false}
}
async function toggle(){if(!task.value)return;busy.value=true;try{const updated=await api.taskAction(projectId,taskId,task.value.status==='paused'?'resume':'pause');taskData.value=updated;paused.value=updated.status==='paused';app.toast(updated.status==='paused'?'任务已暂停':'任务已继续','状态已通过后端更新。')}catch(error){app.toast('操作失败',error instanceof Error?error.message:'请稍后重试')}finally{busy.value=false}}
async function cancelTask(){busy.value=true;try{const updated=await api.taskAction(projectId,taskId,'cancel');taskData.value=updated;app.toast('任务已终止','任务状态已更新为已取消。')}catch(error){app.toast('操作失败',error instanceof Error?error.message:'请稍后重试')}finally{busy.value=false}}
async function submit(){if(!intervention.value.trim())return;try{const result=await api.intervene(projectId,taskId,intervention.value.trim());interventions.value.unshift({time:'刚刚',text:result.content,status:'已提交，等待智能体处理'});intervention.value='';app.toast('指令已提交','将在智能体下一安全阶段注入执行上下文。')}catch(error){app.toast('提交失败',error instanceof Error?error.message:'任务已结束时无法追加指令')}}
onMounted(load)
</script>

<template>
  <div class="content-width task-detail-page">
    <button class="back-link" @click="router.push(`/projects/${projectId}/tasks`)"><ArrowLeft :size="16"/>返回任务树</button>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else-if="task">
      <section class="task-detail-hero">
        <div class="detail-agent-avatar">{{task.agentShort}}<i v-if="task.status==='in_progress'"></i></div>
        <div class="detail-task-copy"><div><StatusBadge :status="paused?'paused':task.status"/><span class="incremental-tag">{{task.incremental?'增量任务':'初始任务'}}</span><span class="task-id">TASK-{{task.id.toUpperCase()}}</span></div><h1>{{task.name}}</h1><p>{{task.description}}</p><span><Bot :size="14"/>执行者：{{task.agent}}</span><span><Clock3 :size="14"/>开始于 {{task.startedAt}}</span></div>
        <div class="detail-actions"><button class="button secondary" :disabled="busy" @click="toggle"><Play v-if="paused" :size="16"/><Pause v-else :size="16"/>{{paused?'继续':'暂停'}}</button><button class="button danger-ghost" :disabled="busy||task.status==='completed'||task.status==='cancelled'" @click="cancelTask"><XCircle :size="16"/>终止</button></div>
      </section>
      <div class="detail-progress-bar"><div><span>任务进度</span><strong>{{task.progress}}%</strong></div><div><i :style="{width:`${task.progress}%`}"></i></div><p><span>状态：{{task.status}}</span><span>已运行 {{task.duration}}</span><span>Token <b>{{task.tokens||'—'}}</b></span></p></div>

      <div class="task-detail-grid">
        <section class="execution-panel">
          <header class="panel-title"><div><h3>执行日志</h3><p>真实 Agent 执行记录</p></div></header>
          <div class="log-toolbar"><div class="live-state"><i v-if="task.status==='in_progress'"></i>{{task.status==='in_progress'?'执行中':'已结束'}}</div><div><button v-for="item in ['全部日志','system','info','tool','success']" :key="item" :class="{active:logFilter===item}" @click="logFilter=item">{{item}}</button></div></div>
          <div class="log-viewer">
            <div v-for="(log,index) in filteredLogs" :key="log.id || index" class="log-row" :class="`log-${log.type}`"><time>{{formatLogTime(log.time)}}</time><span class="log-type">{{log.type.toUpperCase()}}</span><p>{{log.text}}</p></div>
            <div v-if="!filteredLogs.length" class="deployment-empty-row">暂无执行日志</div>
          </div>
        </section>
        <aside class="intervention-panel">
          <div class="intervention-head"><div><h3>人工干预</h3><p>向当前智能体追加优先指令</p></div></div>
          <div class="intervention-compose"><textarea v-model="intervention" placeholder="输入指令，例如：请增加空数据导出的边界测试…"/><div><button class="button primary" :disabled="busy||task.status==='completed'||task.status==='cancelled'||!intervention.trim()" @click="submit"><Send :size="15"/>发送指令</button></div></div>
          <div class="intervention-history"><h4>干预记录 <span>{{interventions.length}}</span></h4><div v-for="(item,index) in interventions" :key="index" class="history-item"><span class="avatar small">{{app.currentUser?.displayName.slice(0,1).toUpperCase()||'U'}}</span><div><p>{{item.text}}</p><small>{{item.time}}</small><span>{{item.status}}</span></div></div><div v-if="!interventions.length" class="deployment-empty-row">暂无人工指令</div></div>
        </aside>
      </div>
    </template>
    <div v-else-if="loading" class="admin-empty"><p><LoaderCircle :size="15" class="spin"/> 正在加载任务详情…</p></div>
  </div>
</template>
