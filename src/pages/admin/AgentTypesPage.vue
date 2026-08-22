<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bot, Copy, Plus, Search, ShieldCheck, Trash2, X } from 'lucide-vue-next'
import { api, type AgentTypeRecord } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'

const router=useRouter();const app=useAppStore()
const agents=ref<AgentTypeRecord[]>([]);const loading=ref(false);const search=ref('');const errorMessage=ref('')
const pendingDelete=ref<AgentTypeRecord|null>(null);const deleting=ref(false)
const COLORS=['#6255d9','#3984df','#8b5bd9','#129c71','#d68a21','#2aa3a3','#5d6b83','#c05b7a']
const filtered=computed(()=>agents.value.filter(a=>`${a.displayName}${a.name}${a.description}${a.model}`.toLowerCase().includes(search.value.toLowerCase())))
const metrics=computed(()=>({
  total:agents.value.length,
  active:agents.value.filter(a=>a.isActive).length,
  templates:agents.value.filter(a=>a.isTemplate).length,
  skills:new Set(agents.value.flatMap(a=>a.skills)).size,
}))
async function load(){loading.value=true;errorMessage.value='';try{agents.value=await api.agentTypes()}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载智能体类型'}finally{loading.value=false}}
async function toggle(agent:AgentTypeRecord){try{const updated=await api.updateAgentType(agent.id,{isActive:!agent.isActive});const index=agents.value.findIndex(a=>a.id===agent.id);if(index>=0)agents.value[index]=updated;app.toast(updated.isActive?'智能体已启用':'智能体已停用',`${updated.displayName} 已更新为配置版本 v${updated.version}。`)}catch(error){app.toast('操作失败',error instanceof Error?error.message:'请确认该智能体未被流程模板引用')}}
async function remove(){if(!pendingDelete.value)return;deleting.value=true;try{const target=pendingDelete.value;await api.deleteAgentType(target.id);agents.value=agents.value.filter(a=>a.id!==target.id);app.toast('已删除',`${target.displayName} 已从平台移除。`);pendingDelete.value=null}catch(error){app.toast('删除失败',error instanceof Error?error.message:'该智能体正在被流程或任务使用')}finally{deleting.value=false}}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page agents-page">
    <PageTitle eyebrow="AGENT STUDIO" title="智能体类型" description="管理平台可用的专业智能体角色、模型、工具与 Skills 装配。">
      <button class="button primary" @click="router.push('/admin/agent-types/new')"><Plus :size="16"/>创建智能体</button>
    </PageTitle>
    <div class="admin-metrics">
      <article><span class="metric-icon indigo"><Bot :size="19"/></span><div><small>智能体类型</small><strong>{{metrics.total}}</strong><em>含系统预置与自定义</em></div></article>
      <article><span class="metric-icon green"><ShieldCheck :size="19"/></span><div><small>已启用</small><strong>{{metrics.active}}</strong><em>可用于流程编排</em></div></article>
      <article><span class="metric-icon blue"><Copy :size="19"/></span><div><small>流程模板</small><strong>{{metrics.templates}}</strong><em>由预置类型构成</em></div></article>
      <article><span class="metric-icon amber"><Bot :size="19"/></span><div><small>已装配 Skills</small><strong>{{metrics.skills}}</strong><em>按类型去重统计</em></div></article>
    </div>
    <section class="panel agent-list-panel">
      <header class="table-toolbar">
        <div class="inline-search admin-search"><Search :size="15"/><input v-model="search" placeholder="搜索名称、标识、说明或模型"/></div>
        <div><button class="filter-button" @click="load"><Bot :size="14"/>{{loading?'加载中…':'刷新'}}</button></div>
      </header>
      <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
      <table v-else-if="loading" class="data-table agent-type-table">
        <thead><tr><th>智能体</th><th>职责说明</th><th>模型</th><th>工具 / Skills</th><th>配置版本</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="row in 6" :key="row">
            <td><div class="member-cell"><span class="skeleton skeleton-avatar"></span><div style="flex:1"><div class="skeleton skeleton-cell" style="width:80px"></div><div class="skeleton skeleton-cell" style="width:110px"></div></div></div></td>
            <td><div class="skeleton skeleton-cell" style="width:180px"></div></td>
            <td><span class="skeleton skeleton-chip"></span></td>
            <td><span class="skeleton skeleton-chip"></span><span class="skeleton skeleton-chip" style="width:48px;margin-left:5px"></span></td>
            <td><div class="skeleton skeleton-cell" style="width:40px"></div></td>
            <td><span class="skeleton skeleton-chip" style="width:40px"></span></td>
            <td></td>
          </tr>
        </tbody>
      </table>
      <table v-else class="data-table agent-type-table">
        <thead><tr><th>智能体</th><th>职责说明</th><th>模型</th><th>工具 / Skills</th><th>配置版本</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(agent,index) in filtered" :key="agent.id">
            <td><div class="member-cell"><span class="agent-type-avatar" :style="{background:COLORS[index%COLORS.length]}">{{agent.displayName.slice(0,2)}}</span><div><b>{{agent.displayName}}</b><small>{{agent.name}}</small></div></div></td>
            <td><div class="agent-desc-cell"><span>{{agent.description}}</span></div></td>
            <td><code class="model-chip">{{agent.model}}</code></td>
            <td><span class="role-chip">{{agent.tools.length}} 工具</span><span class="role-chip manager" style="margin-left:5px">{{agent.skills.length}} Skills</span></td>
            <td><code>v{{agent.version}}</code><small v-if="agent.isTemplate" style="margin-left:6px" class="role-chip owner">预置</small></td>
            <td><button class="toggle-control" :class="{on:agent.isActive}" :title="agent.isActive?'停用':'启用'" @click="toggle(agent)"><i></i></button></td>
            <td><div class="row-actions"><button class="button subtle" @click="router.push(`/admin/agent-types/${agent.id}`)">配置</button><button class="button danger-ghost" @click="pendingDelete=agent"><Trash2 :size="14"/></button></div></td>
          </tr>
          <tr v-if="!loading && !filtered.length"><td colspan="7" class="deployment-empty-row">没有匹配的智能体类型</td></tr>
        </tbody>
      </table>
    </section>
    <div v-if="pendingDelete" class="modal-layer" @click.self="pendingDelete=null">
      <section class="dialog" style="width:min(430px,calc(100vw - 50px))">
        <header class="dialog-head"><div><span class="dialog-kicker">DELETE AGENT TYPE</span><h2>删除智能体类型</h2></div><button class="icon-button" @click="pendingDelete=null"><X :size="18"/></button></header>
        <div class="dialog-body"><p class="dialog-text">确定删除 <b>{{pendingDelete.displayName}}</b>（{{pendingDelete.name}}）吗？被流程模板或运行中任务引用的智能体无法删除，配置版本历史将一并移除。</p></div>
        <footer class="dialog-foot"><span class="dialog-note">此操作不可撤销</span><div style="display:flex;gap:8px"><button class="button ghost" @click="pendingDelete=null">取消</button><button class="button danger-ghost" :disabled="deleting" @click="remove"><Trash2 :size="15"/>{{deleting?'删除中…':'确认删除'}}</button></div></footer>
      </section>
    </div>
  </div>
</template>
