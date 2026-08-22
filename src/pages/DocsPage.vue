<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Database, FileText, History, Network, Rocket, Search, Server, ShieldCheck } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { api, type DocumentRecord } from '../api/client'
import { useAppStore } from '../stores/app'
import PageTitle from '../components/PageTitle.vue'

const route=useRoute();const router=useRouter();const app=useAppStore()
const projectId=String(route.params.id)
const docs=ref<DocumentRecord[]>([]);const loading=ref(false);const errorMessage=ref('')
const active=ref('');const query=ref('')
const TYPE_META:Record<string,{label:string;icon:unknown}>={requirements:{label:'需求说明书',icon:FileText},architecture:{label:'架构设计文档',icon:Network},api:{label:'API 接口文档',icon:Server},database:{label:'数据库设计文档',icon:Database},testing:{label:'测试文档',icon:ShieldCheck},deployment:{label:'部署运维文档',icon:Rocket}}
const grouped=computed(()=>{const map:Record<string,DocumentRecord[]>={};for(const doc of docs.value){(map[doc.documentType]||=[]).push(doc)}return map})
const current=computed(()=>docs.value.find(d=>d.id===active.value)||null)
const currentList=computed(()=>grouped.value[current.value?.documentType||'']||[])
async function load(){loading.value=true;errorMessage.value='';try{docs.value=await api.documents(projectId);if(docs.value.length&&!current.value)active.value=docs.value[0].id}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载项目文档'}finally{loading.value=false}}
onMounted(load)
</script>

<template>
  <div class="content-width docs-page">
    <PageTitle title="项目文档" description="需求、架构、接口与部署文档，随迭代版本化持久保存（真实数据）。">
      <button class="button secondary" @click="load">{{loading?'加载中…':'刷新'}}</button>
      <button class="button primary" @click="router.push(`/projects/${projectId}/requirements`)">需求说明书</button>
    </PageTitle>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <div v-else class="docs-layout">
      <aside class="docs-sidebar panel">
        <div class="docs-search"><Search :size="15"/><input v-model="query" placeholder="搜索文档标题"/></div>
        <nav>
          <template v-for="(items,type) in grouped" :key="type">
            <button v-for="doc in items.filter(d=>d.title.toLowerCase().includes(query.toLowerCase()))" :key="doc.id" :class="{active:active===doc.id}" @click="active=doc.id">
              <span><component :is="TYPE_META[type]?.icon||FileText" :size="16"/></span>
              <div><b>{{doc.title}}</b><small>{{TYPE_META[type]?.label||type}} · v{{doc.version}} · {{new Date(doc.updatedAt).toLocaleDateString('zh-CN')}}</small></div>
            </button>
          </template>
          <div v-if="!loading && !docs.length" class="deployment-empty-row" style="padding:18px">暂无文档 · 构建完成后智能体将自动生成项目文档</div>
        </nav>
      </aside>
      <main v-if="current" class="docs-reader panel">
        <header><div><span class="doc-large-icon"><component :is="TYPE_META[current.documentType]?.icon||FileText" :size="21"/></span><div><h2>{{current.title}}</h2><p>{{TYPE_META[current.documentType]?.label||current.documentType}} · v{{current.version}} · 更新于 {{new Date(current.updatedAt).toLocaleString('zh-CN',{hour12:false})}}</p></div></div><div><button><History :size="15"/>版本 {{current.version}} / {{currentList.length}}</button></div></header>
        <pre class="doc-markdown">{{current.contentMarkdown}}</pre>
      </main>
      <aside v-else class="doc-meta panel"><div class="deployment-empty-row" style="padding:28px">从左侧选择文档查看内容</div></aside>
    </div>
  </div>
</template>
