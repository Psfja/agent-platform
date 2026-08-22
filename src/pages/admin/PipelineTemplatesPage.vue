<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { Bot, Check, Copy, LayoutTemplate, Network, Plus, RefreshCcw, ShieldCheck, Wand2, X } from 'lucide-vue-next'
import { api, ApiError, type AgentTypeRecord, type PipelineDraftRecord, type PipelineNodeRecord, type PipelineTemplateRecord } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'
import FlowCanvas from '../../components/FlowCanvas.vue'

const app=useAppStore()
const templates=ref<PipelineTemplateRecord[]>([]);const agentTypes=ref<AgentTypeRecord[]>([]);const loading=ref(false);const errorMessage=ref('')
const TYPE_LABELS:{[key:string]:string}={fullstack:'Web 全栈应用',api:'API 后端服务',frontend:'前端应用',custom:'自定义流程'}
const EXAMPLE_REQUIREMENTS=[
  '员工报销单据自动审核：抽取发票字段、校验费用标准、生成台账并通知财务复核',
  '供应商准入评估：采集公开信息、比对风险规则、生成评分报告并提交人工审批',
  '每日销售数据报表：从数据库汇总销售数据、核对异常波动、生成日报并推送群通知',
]

const metrics=computed(()=>({total:templates.value.length,active:templates.value.filter(t=>t.isActive).length,system:templates.value.filter(t=>t.isSystem).length,nodes:templates.value.reduce((sum,t)=>sum+t.nodes.length,0)}))

async function load(){loading.value=true;errorMessage.value='';try{[templates.value,agentTypes.value]=await Promise.all([api.pipelineTemplates(),api.agentTypes()]);if(!selectedAgentId.value&&agentTypes.value.length)selectedAgentId.value=agentTypes.value[0].name}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载流程模板'}finally{loading.value=false}}

async function toggle(template:PipelineTemplateRecord){try{const updated=await api.updatePipelineTemplate(template.id,{displayName:template.displayName,description:template.description,templateType:template.templateType as 'fullstack'|'api'|'frontend'|'custom',isActive:!template.isActive,nodes:template.nodes});const index=templates.value.findIndex(t=>t.id===template.id);if(index>=0)templates.value[index]=updated;app.toast(updated.isActive?'模板已启用':'模板已停用',`${updated.displayName} 已更新为 v${updated.version}。`)}catch(error){app.toast('操作失败',error instanceof Error?error.message:'模板引用校验未通过')}}

// ===== AI 生成 =====
const showGenerate=ref(false);const generateLoading=ref(false);const generateError=ref('');const requirement=ref('')
const genWarnings=ref<string[]>([])

async function generate(){
  if(requirement.value.trim().length<8){generateError.value='请提供至少 8 个字符的流程需求描述';return}
  generateLoading.value=true;generateError.value=''
  try{
    const result=await api.generatePipeline(requirement.value.trim())
    draft.value={name:result.draft.name,displayName:result.draft.displayName,description:result.draft.description,templateType:result.draft.templateType,nodes:result.draft.nodes.map(n=>({...n,config:{...n.config}}))}
    genWarnings.value=result.warnings||[]
    editingTemplate.value=null
    showGenerate.value=false
    showEditor.value=true
    await nextTick()
    canvasRef.value?.autoLayout()
    app.toast('流程已生成',`AI 已生成 ${draft.value.nodes.length} 个节点，可在画布上拖拽调整。`)
  }catch(error){generateError.value=error instanceof ApiError?`${error.message}${error.status===503?'：请在 backend/.env 配置 LLM_API_KEY 后重启 API':''}`:error instanceof Error?error.message:'生成失败'}
  finally{generateLoading.value=false}
}
function openGenerate(){showGenerate.value=true;generateError.value='';genWarnings.value=[];requirement.value=''}

// ===== 流程图编辑器 =====
const showEditor=ref(false);const editingTemplate=ref<PipelineTemplateRecord|null>(null);const saving=ref(false);const editorError=ref('')
const draft=ref<PipelineDraftRecord>({name:'',displayName:'',description:'',templateType:'custom',nodes:[]})
const canvasRef=ref<InstanceType<typeof FlowCanvas>|null>(null)
const selectedNodeKey=ref<string|null>(null)
const agentOptions=computed(()=>agentTypes.value.map(a=>({id:a.name,name:a.displayName})))
const selectedNode=computed(()=>draft.value.nodes.find(n=>n.nodeKey===selectedNodeKey.value)||null)
const otherNodes=computed(()=>selectedNode.value?draft.value.nodes.filter(n=>n.nodeKey!==selectedNode.value!.nodeKey):[])
const canSave=computed(()=>draft.value.displayName.trim().length>=2&&draft.value.nodes.length>0&&(editingTemplate.value!==null||/^[a-z][a-z0-9-]{1,79}$/.test(draft.value.name.trim())))

function openCreate(){editingTemplate.value=null;genWarnings.value=[];editorError.value='';draft.value={name:'',displayName:'',description:'',templateType:'custom',nodes:[]};selectedNodeKey.value=null;showEditor.value=true}
function openEdit(template:PipelineTemplateRecord){editingTemplate.value=template;genWarnings.value=[];editorError.value='';draft.value={name:template.name,displayName:template.displayName,description:template.description,templateType:template.templateType,nodes:template.nodes.map(n=>({...n,config:{...n.config},dependsOn:[...n.dependsOn]}))};selectedNodeKey.value=template.nodes[0]?.nodeKey||null;showEditor.value=true}
function closeEditor(){showEditor.value=false;selectedNodeKey.value=null}
const selectedAgentId=ref('')
function addNode(){
  const agent=agentTypes.value.find(a=>a.name===selectedAgentId.value&&a.isActive)||agentTypes.value.find(a=>a.isActive)||agentTypes.value[0]
  if(!agent){app.toast('无可用智能体','请先在智能体管理页创建并启用智能体类型。');return}
  let index=draft.value.nodes.length+1
  let key=`node-${index}`
  while(draft.value.nodes.some(n=>n.nodeKey===key)){index+=1;key=`node-${index}`}
  const node:PipelineNodeRecord={nodeKey:key,agentTypeId:agent.name,displayName:agent.displayName,dependsOn:[],executionMode:'sequential',config:{},position:draft.value.nodes.length}
  draft.value.nodes.push(node)
  selectedNodeKey.value=key
  nextTick(()=>canvasRef.value?.autoLayout())
}
function toggleDep(depKey:string){
  if(!selectedNode.value)return
  if(selectedNode.value.dependsOn.includes(depKey))selectedNode.value.dependsOn=selectedNode.value.dependsOn.filter(d=>d!==depKey)
  else selectedNode.value.dependsOn=[...selectedNode.value.dependsOn,depKey]
}
async function save(){
  saving.value=true;editorError.value=''
  const nodes=draft.value.nodes.map((node,index)=>({...node,dependsOn:[...node.dependsOn],position:index}))
  try{
    if(editingTemplate.value){
      const updated=await api.updatePipelineTemplate(editingTemplate.value.id,{displayName:draft.value.displayName.trim(),description:draft.value.description.trim(),templateType:draft.value.templateType as 'fullstack'|'api'|'frontend'|'custom',isActive:editingTemplate.value.isActive,nodes})
      const idx=templates.value.findIndex(t=>t.id===updated.id);if(idx>=0)templates.value[idx]=updated
      app.toast('流程已保存',`${updated.displayName} 已更新为 v${updated.version}。`)
    }else{
      const created=await api.createPipelineTemplate({name:draft.value.name.trim(),displayName:draft.value.displayName.trim(),description:draft.value.description.trim(),templateType:draft.value.templateType as 'fullstack'|'api'|'frontend'|'custom',isActive:true,nodes})
      templates.value.push(created)
      app.toast('流程已创建',`${created.displayName} 已保存为 v${created.version}。`)
    }
    showEditor.value=false
    selectedNodeKey.value=null
  }catch(error){editorError.value=error instanceof ApiError?error.message:error instanceof Error?error.message:'保存失败'}
  finally{saving.value=false}
}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page templates-page">
    <PageTitle eyebrow="AGENT STUDIO" title="流程编排" description="用自然语言描述需求由 AI 生成流程，或在流程图上拖拽节点手工编排多智能体协作。">
      <button class="button secondary" @click="openCreate"><Plus :size="16"/>手动创建</button>
      <button class="button primary" @click="openGenerate"><Wand2 :size="16"/>AI 生成流程</button>
    </PageTitle>
    <div class="admin-metrics">
      <article><span class="metric-icon indigo"><LayoutTemplate :size="19"/></span><div><small>流程模板</small><strong>{{metrics.total}}</strong><em>含系统预置与自定义</em></div></article>
      <article><span class="metric-icon green"><ShieldCheck :size="19"/></span><div><small>已启用</small><strong>{{metrics.active}}</strong><em>可用于项目创建</em></div></article>
      <article><span class="metric-icon blue"><Copy :size="19"/></span><div><small>系统预置</small><strong>{{metrics.system}}</strong><em>随平台初始化</em></div></article>
      <article><span class="metric-icon amber"><Network :size="19"/></span><div><small>流程节点</small><strong>{{metrics.nodes}}</strong><em>全部模板合计</em></div></article>
    </div>
    <section class="panel agent-list-panel">
      <header class="table-toolbar"><div><strong>模板与节点依赖</strong><span>保存时校验智能体引用与依赖关系</span></div><div><button class="filter-button" @click="load"><RefreshCcw :size="14"/>{{loading?'加载中…':'刷新'}}</button></div></header>
      <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
      <table v-else class="data-table">
        <thead><tr><th>模板</th><th>类型</th><th>节点流程</th><th>版本</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="template in templates" :key="template.id">
            <td><div class="member-cell"><span class="agent-type-avatar" style="background:#3984df">{{template.displayName.slice(0,2)}}</span><div><b>{{template.displayName}}<em v-if="template.isSystem">预置</em></b><small>{{template.name}}</small></div></div></td>
            <td><span class="role-chip manager">{{TYPE_LABELS[template.templateType]||template.templateType}}</span></td>
            <td><div class="template-node-flow"><template v-for="(node,index) in template.nodes" :key="node.nodeKey"><span :title="`${node.displayName}${node.dependsOn.length?`（依赖 ${node.dependsOn.join(', ')}）`:''}`">{{node.displayName}}</span><i v-if="index<template.nodes.length-1" :class="{parallel:node.executionMode==='parallel'}">→</i></template><small v-if="!template.nodes.length" class="field-hint">无节点</small></div></td>
            <td><code>v{{template.version}}</code></td>
            <td><button class="toggle-control" :class="{on:template.isActive}" @click="toggle(template)"><i></i></button></td>
            <td><div class="row-actions"><button class="button subtle" @click="openEdit(template)">编辑</button></div></td>
          </tr>
          <tr v-if="!loading && !templates.length"><td colspan="6" class="deployment-empty-row">暂无流程模板 · 使用「AI 生成流程」从需求描述开始</td></tr>
        </tbody>
      </table>
    </section>

    <!-- AI 生成流程 -->
    <div v-if="showGenerate" class="modal-layer" @click.self="showGenerate=false">
      <section class="dialog flow-dialog">
        <header class="dialog-head"><div><span class="dialog-kicker">AI FLOW DESIGNER</span><h2>AI 生成流程编排</h2></div><button class="icon-button" @click="showGenerate=false"><X :size="18"/></button></header>
        <div class="dialog-body">
          <div v-if="generateError" class="login-error">{{generateError}}</div>
          <label class="form-label">用自然语言描述需要自动化的业务流程<em> *</em></label>
          <textarea class="form-textarea flow-requirement" v-model="requirement" placeholder="例如：员工报销单据自动审核，先抽取发票字段，再校验费用标准，生成台账并通知财务复核…"/>
          <div class="flow-example-chips"><span>示例：</span><button v-for="example in EXAMPLE_REQUIREMENTS" :key="example" @click="requirement=example">{{example.slice(0,18)}}…</button></div>
          <div class="smart-tip"><Bot :size="16"/><div><b>AI 将引用平台真实的智能体类型</b><span>生成结果以流程图呈现，可继续拖拽节点调整依赖与顺序后再保存；需要已配置模型网关（LLM_API_KEY），不会使用模拟结果。</span></div></div>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">生成后进入流程图编辑器人工确认</span><div style="display:flex;gap:8px"><button class="button ghost" @click="showGenerate=false">取消</button><button class="button primary" :disabled="generateLoading||requirement.trim().length<8" @click="generate"><Wand2 :size="15"/>{{generateLoading?'AI 生成中…':'生成流程图'}}</button></div></footer>
      </section>
    </div>

    <!-- 流程图编辑器 -->
    <div v-if="showEditor" class="modal-layer" @click.self="closeEditor">
      <section class="dialog flow-dialog flow-editor-dialog">
        <header class="dialog-head"><div><span class="dialog-kicker">{{editingTemplate?'EDIT PIPELINE':'FLOW EDITOR'}}</span><h2>{{editingTemplate?`编辑 · ${editingTemplate.displayName}`:'流程编排编辑器'}}</h2></div><button class="icon-button" @click="closeEditor"><X :size="18"/></button></header>
        <div class="dialog-body flow-editor-body">
          <div v-if="editorError" class="login-error">{{editorError}}</div>
          <div v-if="genWarnings.length" class="flow-warnings"><b><ShieldCheck :size="14"/>AI 生成时自动修正：</b><ul><li v-for="(warning,index) in genWarnings" :key="index">{{warning}}</li></ul></div>
          <div class="flow-fields">
            <label class="form-label">流程标识<em v-if="!editingTemplate"> *</em><input class="form-input" v-model="draft.name" :disabled="!!editingTemplate" :placeholder="editingTemplate?'':'invoice-audit-flow'"/><span v-if="!editingTemplate" class="field-hint">小写字母开头，可含数字与连字符</span></label>
            <label class="form-label">显示名称<em> *</em><input class="form-input" v-model="draft.displayName" placeholder="发票自动审核流程"/></label>
            <label class="form-label">流程类型<select class="form-input" v-model="draft.templateType"><option v-for="(label,key) in TYPE_LABELS" :key="key" :value="key">{{label}}</option></select></label>
            <label class="form-label full">流程说明<textarea class="form-textarea flow-desc" v-model="draft.description" placeholder="描述该流程适用的业务场景与执行顺序"/></label>
          </div>
          <div class="flow-toolbar">
            <div><select v-model="selectedAgentId" class="form-input" style="width:200px"><option v-for="agent in agentOptions" :key="agent.id" :value="agent.id">{{agent.name}}</option></select><button class="button secondary" @click="addNode"><Plus :size="14"/>添加节点</button><button class="button ghost" @click="canvasRef?.autoLayout()">自动布局</button></div>
            <span class="flow-hint"><ShieldCheck :size="13"/>{{draft.nodes.length}} 个节点 · 拖节点调位置 · 右圆点拖到左圆点建依赖 · 点连线删除</span>
          </div>
          <FlowCanvas ref="canvasRef" v-model="draft.nodes" :agents="agentOptions" @select="selectedNodeKey=$event"/>
          <div v-if="selectedNode" class="flow-inspector">
            <div><label class="form-label">节点名称<input class="form-input" v-model="selectedNode.displayName"/></label></div>
            <div><label class="form-label">执行模式<select class="form-input" v-model="selectedNode.executionMode"><option value="sequential">顺序</option><option value="parallel">并行</option></select></label></div>
            <div class="flow-dep-editor"><label class="form-label">依赖节点（勾选后此节点在其之后执行）</label><div class="flow-dep-chips"><label v-for="other in otherNodes" :key="other.nodeKey" class="chip-check small" :class="{on:selectedNode.dependsOn.includes(other.nodeKey)}"><input type="checkbox" :checked="selectedNode.dependsOn.includes(other.nodeKey)" @change="toggleDep(other.nodeKey)"/><span><Check :size="11"/></span><b>{{other.displayName}}</b></label><small v-if="!otherNodes.length" class="field-hint">暂无其他节点</small></div></div>
          </div>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">{{canSave?'节点与连线将随模板一起保存':'请填写名称并添加至少一个节点'}}</span><div style="display:flex;gap:8px"><button class="button ghost" @click="closeEditor">取消</button><button class="button primary" :disabled="saving||!canSave" @click="save"><Check :size="15"/>{{saving?'保存中…':editingTemplate?'保存修改':'创建模板'}}</button></div></footer>
      </section>
    </div>
  </div>
</template>
