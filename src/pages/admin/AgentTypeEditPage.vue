<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Bot, Check, Puzzle, Save, ShieldCheck, Terminal, Wrench } from 'lucide-vue-next'
import { api, ApiError, type AgentTypeRecord, type SkillRecord } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route=useRoute();const router=useRouter();const app=useAppStore()
const isNew=computed(()=>route.params.id==='new')
const tab=ref('basic');const loading=ref(false);const saving=ref(false);const errorMessage=ref('');const loadError=ref('')
const agent=ref<AgentTypeRecord|null>(null)
const skillsCatalog=ref<SkillRecord[]>([])
const name=ref('');const displayName=ref('');const description=ref('');const model=ref('deepseek-chat');const systemPrompt=ref('')
const tools=ref<string[]>(['read_file','write_file','shell'])
const skills=ref<string[]>([])
const cpu=ref(2);const memory=ref(512);const timeout=ref(60);const isActive=ref(true)

const TOOL_OPTIONS=[
  {key:'read_file',label:'文件读取',description:'读取工作区文件'},
  {key:'write_file',label:'文件写入',description:'创建与修改文件'},
  {key:'shell',label:'Shell 执行',description:'在沙箱中执行命令'},
  {key:'git',label:'Git 操作',description:'分支、提交与推送'},
  {key:'http',label:'HTTP 请求',description:'调用外部接口'},
  {key:'database',label:'数据库访问',description:'查询与迁移'},
  {key:'web_search',label:'Web 搜索',description:'检索公开资料'},
  {key:'docker',label:'Docker',description:'镜像构建与容器管理'},
]
const SKILL_LABELS:{[key:string]:string}={'requirement-analysis':'需求分析','code-metrics':'代码度量','regression-plan':'回归测试计划'}
const MODEL_OPTIONS=['deepseek-chat','deepseek-coder','qwen-max','qwen-plus','glm-4-plus']

function applyAgent(item:AgentTypeRecord){agent.value=item;name.value=item.name;displayName.value=item.displayName;description.value=item.description;model.value=item.model;systemPrompt.value=item.systemPrompt;tools.value=[...item.tools];skills.value=[...item.skills];cpu.value=Number(item.sandboxConfig?.cpu||2);memory.value=Number(item.sandboxConfig?.memoryMb||512);timeout.value=Number(item.sandboxConfig?.timeoutSeconds||60);isActive.value=item.isActive}
function toggleItem(list:string[],key:string){const index=list.indexOf(key);if(index>=0)list.splice(index,1);else list.push(key)}
async function load(){loading.value=true;loadError.value='';try{skillsCatalog.value=await api.skills();if(!isNew.value){const item=await api.agentType(String(route.params.id));applyAgent(item)}}catch(error){loadError.value=error instanceof Error?error.message:'无法加载配置'}finally{loading.value=false}}
async function save(){
  saving.value=true;errorMessage.value=''
  const sandboxConfig={cpu:Number(cpu.value)||2,memoryMb:Number(memory.value)||512,timeoutSeconds:Number(timeout.value)||60}
  const payload={displayName:displayName.value.trim(),description:description.value.trim(),systemPrompt:systemPrompt.value.trim(),model:model.value,tools:[...tools.value],skills:[...skills.value],sandboxConfig,isActive:isActive.value}
  try{
    if(isNew.value){await api.createAgentType({name:name.value.trim(),...payload});app.toast('创建成功',`${displayName.value} 已创建为配置版本 v1。`)}
    else{const updated=await api.updateAgentType(String(route.params.id),payload);applyAgent(updated);app.toast('配置已保存',`${updated.displayName} 已更新为配置版本 v${updated.version}。`);router.push('/admin/agent-types')}
    if(isNew.value)router.push('/admin/agent-types')
  }catch(error){
    if(error instanceof ApiError)errorMessage.value=`${error.message}${error.details?`（${JSON.stringify(error.details)}）`:''}`
    else errorMessage.value=error instanceof Error?error.message:'保存失败'
  }finally{saving.value=false}
}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page agent-edit-page">
    <PageTitle :eyebrow="isNew?'CREATE AGENT TYPE':'AGENT TYPE CONFIGURATION'" :title="isNew?'创建智能体类型':(agent?.displayName||'智能体配置')" :description="isNew?'定义新的专业角色、能力与运行环境。':(agent?.name||'')+' · 配置版本 v'+(agent?.version||'—')">
      <template v-if="agent"><StatusBadge :status="agent.isActive?'completed':'paused'" :label="agent.isActive?'已启用':'已停用'"/></template>
      <button class="button primary" :disabled="saving||loading" @click="save"><Save :size="16"/>{{saving?'保存中…':'保存配置'}}</button>
    </PageTitle>
    <div v-if="loadError" class="admin-empty"><p>{{loadError}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else>
      <section class="panel">
        <div class="agent-edit-tabs">
          <button v-for="item in [['basic','基础信息',Bot],['prompt','系统提示词',Terminal],['capabilities','工具与技能',Wrench],['sandbox','沙箱环境',ShieldCheck],['stats','配置信息',Puzzle]] as const" :key="item[0]" :class="{active:tab===item[0]}" @click="tab=item[0]"><component :is="item[2]" :size="14"/>{{item[1]}}</button>
        </div>
        <div v-if="errorMessage" class="login-error" style="margin:13px 15px 0">{{errorMessage}}</div>
        <div class="agent-edit-form">
          <template v-if="tab==='basic'">
            <div class="form-field full"><label class="form-label">类型标识<em> *</em></label><input class="form-input" v-model="name" :disabled="!isNew" placeholder="backend-developer"/><p class="field-hint">{{isNew?'小写字母、数字与连字符，创建后不可修改':'类型标识创建后不可修改'}}</p></div>
            <div class="form-field"><label class="form-label">显示名称<em> *</em></label><input class="form-input" v-model="displayName" placeholder="后端开发工程师"/></div>
            <div class="form-field"><label class="form-label">默认模型<em> *</em></label><select class="form-input" v-model="model"><option v-for="item in MODEL_OPTIONS" :key="item" :value="item">{{item}}</option></select></div>
            <div class="form-field full"><label class="form-label">职责说明<em> *</em></label><textarea class="form-textarea" v-model="description" placeholder="描述该智能体负责的工作范围与协作方式"/></div>
            <label class="form-field full toggle-row"><input type="checkbox" v-model="isActive"/><span class="toggle-control" :class="{on:isActive}"><i></i></span><div><b>启用该智能体类型</b><small>停用后无法在新流程模板中引用</small></div></label>
          </template>
          <template v-else-if="tab==='prompt'">
            <div class="form-field full"><label class="form-label">系统提示词<em> *</em></label><textarea class="form-textarea prompt-textarea" v-model="systemPrompt" placeholder="定义该智能体的角色、职责、约束与输出要求…"/><p class="field-hint">提示词将作为 DeepAgents SubAgent 的 system prompt 注入。</p></div>
          </template>
          <template v-else-if="tab==='capabilities'">
            <div class="form-field full"><label class="form-label">工具能力</label><div class="chip-grid"><label v-for="tool in TOOL_OPTIONS" :key="tool.key" class="chip-check" :class="{on:tools.includes(tool.key)}"><input type="checkbox" :checked="tools.includes(tool.key)" @change="toggleItem(tools,tool.key)"/><span><Check :size="11"/></span><div><b>{{tool.label}}</b><small>{{tool.description}}</small></div></label></div></div>
            <div class="form-field full"><label class="form-label">Skills 装配</label><div class="chip-grid skills"><label v-for="skill in skillsCatalog" :key="skill.name" class="chip-check" :class="{on:skills.includes(skill.name)}"><input type="checkbox" :checked="skills.includes(skill.name)" @change="toggleItem(skills,skill.name)"/><span><Check :size="11"/></span><div><b>{{skill.displayName||skill.name}}</b><small>{{skill.name}}@{{skill.version}} · {{skill.executable?'沙箱可执行':'Prompt 指令'}}</small></div></label><p v-if="!skillsCatalog.length" class="field-hint">尚未加载任何 Skills，可在「Skill 管理与装配」页扫描目录。</p></div></div>
          </template>
          <template v-else-if="tab==='sandbox'">
            <div class="form-field"><label class="form-label">CPU 核数</label><input class="form-input" v-model.number="cpu" type="number" min="1" max="16"/></div>
            <div class="form-field"><label class="form-label">内存上限（MB）</label><input class="form-input" v-model.number="memory" type="number" min="64" max="8192" step="64"/></div>
            <div class="form-field"><label class="form-label">执行超时（秒）</label><input class="form-input" v-model.number="timeout" type="number" min="10" max="3600"/></div>
            <div class="form-field full"><div class="smart-tip"><ShieldCheck :size="16"/><div><b>沙箱隔离说明</b><span>Skill 代码与生成代码仅在沙箱执行；本地进程沙箱仅提供资源限制，生产环境请配置 Docker 沙箱以获得网络与文件系统隔离。</span></div></div></div>
          </template>
          <template v-else>
            <div class="form-field full"><div class="confirm-list"><div><dt>类型标识</dt><dd>{{agent?.name||name||'—'}}</dd></div><div><dt>配置版本</dt><dd>v{{agent?.version||'1（待创建）'}}</dd></div><div><dt>是否预置</dt><dd>{{agent?.isTemplate?'是':'否'}}</dd></div><div><dt>工具 / Skills</dt><dd>{{tools.length}} / {{skills.length}}</dd></div></div></div>
            <div class="form-field"><label class="form-label">创建时间</label><div class="field-readonly">{{agent?new Date(agent.createdAt).toLocaleString('zh-CN',{hour12:false}):'—'}}</div></div>
            <div class="form-field"><label class="form-label">更新时间</label><div class="field-readonly">{{agent?new Date(agent.updatedAt).toLocaleString('zh-CN',{hour12:false}):'—'}}</div></div>
          </template>
        </div>
        <footer class="agent-edit-foot"><button class="button ghost" @click="router.push('/admin/agent-types')"><ArrowLeft :size="15"/>返回列表</button><button class="button primary" :disabled="saving||loading" @click="save"><Save :size="16"/>{{saving?'保存中…':'保存配置'}}</button></footer>
      </section>
    </template>
  </div>
</template>
