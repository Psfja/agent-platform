<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, Box, CheckCircle2, Cloud, Cpu, Database, HardDrive, RefreshCcw, Server, Workflow, Zap } from 'lucide-vue-next'
import { api, type MonitoringSummary } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const app=useAppStore()
const summary=ref<MonitoringSummary|null>(null);const loading=ref(false);const errorMessage=ref('')
const queueCounts=computed(()=>{const counts=summary.value?.queue.counts||{};return Object.entries(counts).sort(([a],[b])=>a.localeCompare(b))})
const tokenText=computed(()=>{const tokens=summary.value?.agentBuilds.tokens||0;if(tokens>=1_000_000)return `${(tokens/1_000_000).toFixed(1)}M`;if(tokens>=1_000)return `${(tokens/1_000).toFixed(1)}k`;return String(tokens)})
function percent(value:number){return Math.max(0,Math.min(100,Math.round(value)))}
function trackColor(value:number){return value>=85?'background:var(--red)':value>=65?'background:var(--amber)':'background:var(--green)'}
async function load(){loading.value=true;errorMessage.value='';try{summary.value=await api.monitoringSummary()}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载监控数据（需要平台管理员权限）'}finally{loading.value=false}}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page resources-page">
    <PageTitle eyebrow="PLATFORM ADMIN" title="资源与运行监控" description="平台主机资源、业务指标与任务队列的真实运行状态。">
      <button class="button secondary" @click="load"><RefreshCcw :size="16"/>{{loading?'加载中…':'刷新'}}</button>
    </PageTitle>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else-if="summary">
      <div class="resource-overview">
        <article class="panel resource-card"><div class="resource-card-head"><span class="metric-icon indigo"><Cpu :size="18"/></span><em class="green-text">实时</em></div><small>CPU 使用率</small><strong>{{summary.system.cpuPercent.toFixed(1)}}<em>%</em></strong><div class="resource-track"><i :style="`width:${percent(summary.system.cpuPercent)}%;${trackColor(summary.system.cpuPercent)}`"></i></div><p>主机处理器负载{{summary.system.loadAverage.length?` · 1min ${summary.system.loadAverage[0].toFixed(2)}`:''}}</p></article>
        <article class="panel resource-card"><div class="resource-card-head"><span class="metric-icon blue"><Activity :size="18"/></span><em class="green-text">实时</em></div><small>内存使用率</small><strong>{{summary.system.memoryPercent.toFixed(1)}}<em>%</em></strong><div class="resource-track"><i :style="`width:${percent(summary.system.memoryPercent)}%;${trackColor(summary.system.memoryPercent)}`"></i></div><p>主机物理内存占用</p></article>
        <article class="panel resource-card"><div class="resource-card-head"><span class="metric-icon green"><HardDrive :size="18"/></span><em class="green-text">实时</em></div><small>磁盘使用率</small><strong>{{summary.system.diskPercent.toFixed(1)}}<em>%</em></strong><div class="resource-track"><i :style="`width:${percent(summary.system.diskPercent)}%;${trackColor(summary.system.diskPercent)}`"></i></div><p>根分区空间占用</p></article>
        <article class="panel resource-card"><div class="resource-card-head"><span class="metric-icon amber"><Zap :size="18"/></span><em>累计</em></div><small>Agent Token 消耗</small><strong>{{tokenText}}</strong><div class="resource-track"><i style="width:32%;background:var(--amber)"></i></div><p>全部 Agent Build 的 Prompt + Completion</p></article>
      </div>
      <div class="resource-chart-grid">
        <section class="panel utilization-chart">
          <header class="panel-title"><div><h3>业务运行指标</h3><p>项目、任务、构建与部署统计</p></div></header>
          <div class="business-metrics">
            <div><span class="metric-icon indigo"><Box :size="17"/></span><div><small>项目</small><strong>{{summary.projects.total}}</strong><em>{{summary.projects.active}} 个进行中</em></div></div>
            <div><span class="metric-icon blue"><Workflow :size="17"/></span><div><small>运行中任务</small><strong>{{summary.tasks.running}}</strong><em>{{summary.tasks.failed}} 个失败</em></div></div>
            <div><span class="metric-icon green"><CheckCircle2 :size="17"/></span><div><small>构建完成</small><strong>{{summary.agentBuilds.completed}}</strong><em>{{summary.agentBuilds.failed}} 个失败</em></div></div>
            <div><span class="metric-icon amber"><Server :size="17"/></span><div><small>运行中部署</small><strong>{{summary.deployments.running}}</strong><em>{{summary.deployments.failed}} 个失败</em></div></div>
          </div>
        </section>
        <section class="panel token-breakdown">
          <header class="panel-title"><div><h3>任务队列</h3><p>{{summary.queue.redisAvailable?'Redis 持久队列':'线程降级模式'}} · {{summary.queue.queueName}}</p></div><StatusBadge :status="summary.queue.redisAvailable?'completed':'paused'" :label="summary.queue.redisAvailable?'Redis':'Fallback'"/></header>
          <div class="queue-counts">
            <div v-for="[name,count] in queueCounts" :key="name"><span>{{name}}</span><strong>{{count}}</strong></div>
            <p v-if="!queueCounts.length">暂无排队任务</p>
          </div>
        </section>
      </div>
      <section class="panel active-instances">
        <header class="panel-title"><div><h3>存储与运行环境</h3><p>对象存储、数据库与部署运行时状态</p></div></header>
        <table class="data-table">
          <thead><tr><th>组件</th><th>状态</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><span class="member-cell"><span class="metric-icon indigo" style="width:31px;height:31px"><Cloud :size="15"/></span><b>对象存储</b></span></td><td><StatusBadge :status="summary.storage.configured?'completed':'paused'" :label="summary.storage.provider==='minio'?'MinIO':'本地文件'"/></td><td>{{summary.storage.configured?'MinIO 已连接，产物与附件写入对象存储':'MinIO 未配置，产物与附件降级为本地文件'}}</td></tr>
            <tr><td><span class="member-cell"><span class="metric-icon blue" style="width:31px;height:31px"><Database :size="15"/></span><b>任务队列</b></span></td><td><StatusBadge :status="summary.queue.redisAvailable?'completed':'paused'" :label="summary.queue.redisAvailable?'Redis':'线程降级'"/></td><td>{{summary.queue.redisAvailable?'Redis 持久队列，支持独立 Worker、心跳与孤儿任务恢复':'Redis 不可用，使用开发线程降级执行'}}</td></tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>
