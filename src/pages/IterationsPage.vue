<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, CheckCircle2, ChevronDown, Code2, GitBranch, GitCompareArrows, Plus, RotateCcw, Rocket, Tag, TestTube2 } from 'lucide-vue-next'
import { api } from '../api/client'
import type { Iteration } from '../types'
import { useAppStore } from '../stores/app'
import ChangeRequestDialog from '../components/ChangeRequestDialog.vue'
import PageTitle from '../components/PageTitle.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const router=useRouter();const app=useAppStore();const showChange=ref(false);const expanded=ref('');const filter=ref('全部版本');const iterationItems=ref<Iteration[]>([])
async function load(){try{iterationItems.value=await api.iterations(String(route.params.id));expanded.value=iterationItems.value[0]?.id||''}catch{app.toast('加载失败','无法连接后端服务。')}}
function compare(item:Iteration){const index=iterationItems.value.findIndex(i=>i.id===item.id);const previous=iterationItems.value[index+1];if(!previous){app.toast('无可对比版本','该迭代之前没有历史版本。');return}router.push(`/projects/${route.params.id}/compare?from=${encodeURIComponent(previous.version)}&to=${encodeURIComponent(item.version)}`)}
onMounted(load)
</script>

<template>
  <div class="content-width iterations-page">
    <PageTitle title="迭代历史" description="追踪项目从首次交付到持续演进的每一次变更。">
      <button class="button secondary" @click="router.push(`/projects/${route.params.id}/compare`)"><GitCompareArrows :size="16"/>版本对比</button><button class="button primary" @click="showChange=true"><Plus :size="17"/>提出新需求</button>
    </PageTitle>
    <section class="version-overview">
      <div class="current-version"><span><Tag :size="22"/></span><div><small>最新版本</small><strong>{{iterationItems[0]?.version||'—'}}</strong><p><i></i>{{iterationItems[0]?iterationItems[0].deployStatus:'暂无迭代记录'}}</p></div></div>
      <div class="version-stat"><small>累计迭代</small><strong>{{iterationItems.length}} <em>次</em></strong></div><div class="version-stat"><small>累计变更</small><strong>{{iterationItems.reduce((n,i)=>n+i.files,0)}} <em>文件</em></strong></div><div class="version-stat"><small>平均测试通过</small><strong>{{iterationItems.length?Math.round(iterationItems.reduce((n,i)=>n+i.tests,0)/iterationItems.length):'—'}}<em>%</em></strong></div>
      <div class="evolution-line"><svg viewBox="0 0 180 48" preserveAspectRatio="none"><defs><linearGradient id="spark" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#6255d9" stop-opacity=".22"/><stop offset="1" stop-color="#6255d9" stop-opacity="0"/></linearGradient></defs><path class="area" d="M0 38 C25 35,35 20,58 27 S93 9,117 18 S148 6,180 10 V48 H0Z"/><path d="M0 38 C25 35,35 20,58 27 S93 9,117 18 S148 6,180 10"/></svg><small>交付效率持续提升</small></div>
    </section>
    <div class="iteration-toolbar"><div><button class="active">全部迭代 <span>{{iterationItems.length}}</span></button><button>功能</button><button>修复</button></div><button class="filter-button">{{filter}}<ChevronDown :size="14"/></button></div>
    <section class="timeline">
      <article v-for="(item,index) in iterationItems" :key="item.id" class="iteration-item" :class="[`iteration-${item.status}`,{expanded:expanded===item.id}]">
        <div class="timeline-rail"><span><CheckCircle2 v-if="item.status==='completed'" :size="17"/><span v-else class="running-ring"></span></span><i v-if="index<iterationItems.length-1"></i></div>
        <div class="iteration-card">
          <header @click="expanded=expanded===item.id?'':item.id"><div class="version-badge" :class="`type-${item.type}`"><GitBranch :size="16"/>{{item.version}}</div><div class="iteration-title"><h3>{{item.title}}</h3><p>{{item.description}}</p><div><span>{{item.date}}</span><i></i><span>{{item.author}} 提出</span></div></div><StatusBadge :status="item.status" :label="item.status==='executing'?'执行中':item.status==='analyzing'?'待确认':'已发布'"/><button class="icon-button"><ChevronDown :size="18"/></button></header>
          <div class="iteration-metrics"><span><Code2 :size="15"/><b>{{item.files}}</b> 个文件</span><span class="lines"><b>+{{item.added}}</b> / <em>−{{item.removed}}</em> 行</span><span><TestTube2 :size="15"/><b>{{item.tests}}%</b> 测试通过</span><span><Rocket :size="15"/>{{item.deployStatus}}</span></div>
          <div v-if="expanded===item.id" class="iteration-detail">
            <div class="detail-flow"><div class="done"><span><CheckCircle2 :size="15"/></span><b>影响分析</b><small>已生成报告</small></div><i></i><div :class="item.status==='completed'?'done':'active'"><span><CheckCircle2 v-if="item.status==='completed'" :size="15"/>2</span><b>增量开发</b><small>{{item.status==='completed'?'已完成':'进行中'}}</small></div><i></i><div :class="item.status==='executing'?'active':item.status==='completed'?'done':''"><span><CheckCircle2 v-if="item.status==='completed'" :size="15"/>3</span><b>回归测试</b><small>{{item.status==='executing'?'进行中':item.status==='completed'?'已通过':'待执行'}}</small></div><i></i><div :class="item.status==='completed'?'done':''"><span><CheckCircle2 v-if="item.status==='completed'" :size="15"/>4</span><b>部署</b><small>{{item.deployStatus}}</small></div></div>
            <div class="detail-actions-row"><button class="text-button" @click="router.push(`/projects/${route.params.id}/iterations/${item.id}`)">查看完整详情<ArrowRight :size="15"/></button><button class="text-button" @click="compare(item)"><GitCompareArrows :size="15"/>与上一版本对比</button><button v-if="item.status==='completed'" class="text-button danger-text" @click="app.toast('回滚提示','请在版本对比页完成风险确认后回滚。')"><RotateCcw :size="15"/>回滚到此版本</button></div>
          </div>
        </div>
      </article>
    </section>
    <ChangeRequestDialog v-if="showChange" @close="showChange=false" @submitted="load"/>
  </div>
</template>
