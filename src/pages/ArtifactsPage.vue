<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Box, CheckCircle2, CloudDownload, Code2, ExternalLink, FileCode2, Rocket, Search } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { api, type ApplicationDeploymentRecord, type ArtifactRecord } from '../api/client'
import { useAppStore } from '../stores/app'
import PageTitle from '../components/PageTitle.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const app=useAppStore()
const projectId=String(route.params.id)
const artifacts=ref<ArtifactRecord[]>([]);const deployments=ref<ApplicationDeploymentRecord[]>([]);const loading=ref(false);const errorMessage=ref('');const query=ref('')
const TYPE_LABELS:{[key:string]:string}={generated_app:'代码产物',report:'测试报告',image:'部署镜像',document:'项目文档'}
const TYPE_ICONS:{[key:string]:unknown}={'generated_app':Code2,'report':FileCode2,'image':Box,'document':FileCode2}
const filtered=computed(()=>artifacts.value.filter(a=>`${a.name}${a.type}`.toLowerCase().includes(query.value.toLowerCase())))
const runningDeployment=computed(()=>deployments.value.find(d=>d.status==='running')||null)
function fmtSize(bytes:number):string{if(bytes>=1024*1024)return `${(bytes/1024/1024).toFixed(1)} MB`;if(bytes>=1024)return `${(bytes/1024).toFixed(1)} KB`;return `${bytes} B`}
async function load(){loading.value=true;errorMessage.value='';try{[artifacts.value,deployments.value]=await Promise.all([api.artifacts(projectId),api.applicationDeployments(projectId).catch(()=>[])])}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载产物列表'}finally{loading.value=false}}
function download(item:ArtifactRecord){const buildId=item.metadata?.buildId;if(buildId){window.location.assign(api.agentBuildDownloadUrl(projectId,String(buildId)))}else{app.toast('产物不可下载',`${item.name} 未关联构建记录。`)}}
onMounted(load)
</script>

<template>
  <div class="content-width artifacts-page">
    <PageTitle title="产物中心" description="项目构建生成的源码包、镜像与部署产物（真实数据）。">
      <button class="button secondary" @click="load">{{loading?'加载中…':'刷新'}}</button>
      <a v-if="runningDeployment" class="button primary" :href="runningDeployment.deployUrl" target="_blank" rel="noopener"><ExternalLink :size="16"/>访问应用</a>
    </PageTitle>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else>
      <div class="artifact-metrics">
        <article><span class="metric-icon indigo"><Code2 :size="19"/></span><div><small>构建产物</small><strong>{{artifacts.length}}</strong><span>{{artifacts.reduce((sum,a)=>sum+a.sizeBytes,0)>=1024*1024?fmtSize(artifacts.reduce((sum,a)=>sum+a.sizeBytes,0)):'—'}}</span></div></article>
        <article><span class="metric-icon green"><CheckCircle2 :size="19"/></span><div><small>部署记录</small><strong>{{deployments.length}}</strong><span>{{deployments.filter(d=>d.status==='completed').length}} 次成功</span></div></article>
        <article><span class="metric-icon blue"><Box :size="19"/></span><div><small>运行中部署</small><strong>{{deployments.filter(d=>d.status==='running').length}}</strong><span>{{runningDeployment?`端口 ${runningDeployment.hostPort}`:'无'}}</span></div></article>
        <article><span class="metric-icon amber"><Rocket :size="19"/></span><div><small>最新版本</small><strong>{{deployments[0]?.version||'—'}}</strong><span>{{runningDeployment?runningDeployment.environment:'暂无运行实例'}}</span></div></article>
      </div>
      <div class="artifact-layout">
        <aside class="artifact-nav">
          <button class="active"><Code2 :size="17"/>全部产物<span>{{artifacts.length}}</span></button>
          <button v-for="(label,type) in TYPE_LABELS" :key="type"><component :is="TYPE_ICONS[type]" :size="17"/>{{label}}<span>{{artifacts.filter(a=>a.type===type).length}}</span></button>
        </aside>
        <section class="panel artifact-browser">
          <header class="panel-title"><div><h3>产物列表</h3><p>按构建时间倒序</p></div><div class="inline-search"><Search :size="15"/><input v-model="query" placeholder="搜索产物"/></div></header>
          <div class="document-cards">
            <article v-for="item in filtered" :key="item.id">
              <span><component :is="TYPE_ICONS[item.type]||Box" :size="18"/></span>
              <div><strong>{{item.name}}</strong><p>{{TYPE_LABELS[item.type]||item.type}} · {{fmtSize(item.sizeBytes)}} · {{new Date(item.createdAt).toLocaleString('zh-CN',{hour12:false})}}</p></div>
              <StatusBadge status="completed" label="已就绪"/>
              <button v-if="item.metadata?.buildId" class="button subtle" style="margin-left:10px" @click="download(item)"><CloudDownload :size="14"/>下载</button>
            </article>
            <div v-if="!loading && !filtered.length" class="deployment-empty-row">暂无产物 · 完成一次「AI 全栈构建」后，源码 ZIP 会出现在这里</div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
