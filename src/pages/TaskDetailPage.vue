<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Bot, CheckCircle2, ChevronRight, CirclePause, Clock3, Copy, FileCode2, Files, MessageSquareText, MoreHorizontal, Pause, Play, RotateCcw, Search, Send, Sparkles, Terminal, Wrench, XCircle } from 'lucide-vue-next'
import { taskLogs as fallbackLogs, tasks } from '../data/mock'
import { api, type TaskLogRecord } from '../api/client'
import { useAppStore } from '../stores/app'
import type { Task } from '../types'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const router=useRouter();const app=useAppStore();const projectId=String(route.params.id);const taskId=String(route.params.taskId)
const taskData=ref<Task>(tasks.find(t=>t.id===taskId)||tasks[6]);const task=computed(()=>taskData.value)
const logs=ref<TaskLogRecord[]>(fallbackLogs);const tab=ref('logs');const paused=ref(false);const intervention=ref('');const logFilter=ref('全部日志');
const interventions=ref<{time:string;text:string;status:string}[]>([{time:'11:41',text:'请重点验证 5 万条以上数据导出时的内存占用。',status:'智能体已采纳并加入测试范围'}])
async function load(){
  try{
    const [latest,latestLogs,history]=await Promise.all([api.task(projectId,taskId),api.logs(projectId,taskId),api.interventions(projectId,taskId)])
    taskData.value=latest;paused.value=latest.status==='paused';logs.value=latestLogs
    if(history.length)interventions.value=history.map(item=>({time:new Date(item.createdAt).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}),text:item.content,status:item.agentResponse||item.status}))
  }catch{app.toast('后端连接提示','任务详情继续显示本地演示数据。')}
}
async function toggle(){
  try{taskData.value=await api.taskAction(projectId,taskId,paused.value?'resume':'pause');paused.value=taskData.value.status==='paused';app.toast(paused.value?'任务已暂停':'任务已继续',paused.value?'状态已保存，可随时继续。':'测试工程师已恢复执行。')}catch(error){app.toast('操作失败',error instanceof Error?error.message:'请稍后重试')}
}
async function cancelTask(){try{taskData.value=await api.taskAction(projectId,taskId,'cancel');app.toast('任务已终止','执行上下文与日志已保留。')}catch(error){app.toast('无法终止',error instanceof Error?error.message:'请稍后重试')}}
async function send(){
  const content=intervention.value.trim();if(!content)return
  try{const item=await api.intervene(projectId,taskId,content);interventions.value.unshift({time:'刚刚',text:content,status:item.agentResponse});intervention.value='';app.toast('指令已发送','智能体将在当前操作完成后优先处理。');logs.value=await api.logs(projectId,taskId)}catch(error){app.toast('发送失败',error instanceof Error?error.message:'请稍后重试')}
}
function formatLogTime(value:string){return value.includes('T')?new Date(value).toLocaleTimeString('zh-CN',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}):value}
onMounted(load)
</script>

<template>
  <div class="content-width task-detail-page">
    <button class="back-link" @click="router.push(`/projects/${route.params.id}/tasks`)"><ArrowLeft :size="16"/>返回任务树</button>
    <section class="task-detail-hero">
      <div class="detail-agent-avatar">{{task.agentShort}}<i></i></div>
      <div class="detail-task-copy"><div><StatusBadge :status="paused?'paused':task.status"/><span class="incremental-tag">增量任务</span><span class="task-id">TASK-{{task.id.toUpperCase()}}</span></div><h1>{{task.name}}</h1><p>{{task.description}}</p><span><Bot :size="14"/>执行者：{{task.agent}}</span><span><Clock3 :size="14"/>开始于 {{task.startedAt}}</span></div>
      <div class="detail-actions"><button class="button secondary" @click="toggle"><Play v-if="paused" :size="16"/><Pause v-else :size="16"/>{{paused?'继续':'暂停'}}</button><button class="button danger-ghost" @click="cancelTask"><XCircle :size="16"/>终止</button><button class="icon-button"><MoreHorizontal :size="19"/></button></div>
    </section>
    <div class="detail-progress-bar"><div><span>任务进度</span><strong>{{task.progress}}%</strong></div><div><i :style="{width:`${task.progress}%`}"></i></div><p><span>已完成 <b>104</b> / 152 项测试</span><span>预计剩余 <b>14 分钟</b></span><span>Token <b>{{task.tokens}}</b></span></p></div>

    <div class="task-detail-grid">
      <section class="execution-panel">
        <div class="execution-tabs"><button :class="{active:tab==='logs'}" @click="tab='logs'"><Terminal :size="16"/>执行日志</button><button :class="{active:tab==='artifacts'}" @click="tab='artifacts'"><Files :size="16"/>中间产物 <span>8</span></button><button :class="{active:tab==='calls'}" @click="tab='calls'"><Wrench :size="16"/>工具调用 <span>21</span></button></div>
        <template v-if="tab==='logs'">
          <div class="log-toolbar"><div class="live-state"><i></i>实时更新中</div><div><button>{{logFilter}}<ChevronRight :size="13"/></button><button><Search :size="15"/>搜索</button><button @click="app.toast('日志已复制','执行日志已复制到剪贴板。')"><Copy :size="15"/>复制</button></div></div>
          <div class="log-viewer">
            <div v-for="(log,index) in logs" :key="log.id || index" class="log-row" :class="`log-${log.type}`"><time>{{formatLogTime(log.time)}}</time><span class="log-type">{{log.type.toUpperCase()}}</span><p>{{log.text }}</p></div>
            <div class="log-running"><span></span><span></span><span></span></div>
          </div>
        </template>
        <div v-else-if="tab==='artifacts'" class="artifact-list inner-artifacts">
          <div v-for="file in ['tests/export/test_report_export.py','reports/regression-v1.3.0.html','coverage/coverage.json','logs/e2e-export-flow.log']" :key="file"><span><FileCode2 :size="18"/></span><div><strong>{{file}}</strong><small>由测试工程师生成 · 2 分钟前</small></div><button class="text-button">查看</button></div>
        </div>
        <div v-else class="tool-call-list">
          <div v-for="(item,i) in logs.filter(l=>l.type==='tool')" :key="i"><span><Wrench :size="16"/></span><div><strong>{{item.text.split(' → ')[0]}}</strong><code>{{item.text.split(' → ')[1]}}</code><small>{{item.time}} · 成功 · 1.2s</small></div><StatusBadge status="completed" label="成功"/></div>
        </div>
      </section>

      <aside class="intervention-panel">
        <div class="intervention-head"><div><h3>人工干预</h3><p>向当前智能体追加优先指令</p></div><MessageSquareText :size="20"/></div>
        <div class="intervention-compose"><textarea v-model="intervention" placeholder="输入指令，例如：请增加空数据导出的边界测试…" @keydown.meta.enter="send"></textarea><div><span>⌘ Enter 发送</span><button @click="send" :disabled="!intervention.trim()"><Send :size="15"/>发送指令</button></div></div>
        <div class="quick-actions"><span>快捷操作</span><div><button @click="intervention='请重新检查当前步骤的边界条件。' "><RotateCcw :size="14"/>重做当前步骤</button><button @click="toggle"><CirclePause :size="14"/>{{paused?'继续任务':'暂停任务'}}</button></div></div>
        <div class="intervention-history"><h4>干预记录 <span>{{interventions.length}}</span></h4><div v-for="(item,i) in interventions" :key="i" class="history-item"><span class="avatar small">LJ</span><div><p>{{item.text}}</p><small>{{item.time}} · 林嘉</small><span><CheckCircle2 :size="13"/>{{item.status}}</span></div></div></div>
        <div class="intervention-note"><Sparkles :size="15"/><p>智能体会在当前工具调用完成后处理新指令，所有干预均会记录到项目审计日志。</p></div>
      </aside>
    </div>
  </div>
</template>
