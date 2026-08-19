<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlertCircle, Archive, Check, CheckCircle2, ChevronDown, Clock3, File, FileText, History, Link2, MessageSquareText, MoreHorizontal, Paperclip, Pencil, Plus, Save, Send, Sparkles, Upload, UserRound, X } from 'lucide-vue-next'
import { api } from '../api/client'
import { useAppStore } from '../stores/app'
import PageTitle from '../components/PageTitle.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const app=useAppStore();const projectId=String(route.params.id);const editing=ref(false);const showHistory=ref(false);const persistedVersion=ref(0);const activeSection=ref('overview');const question=ref('');const messages=ref([{role:'ai',text:'需求说明书已同步至 v1.3.0。当前没有阻塞性澄清项。'},{role:'user',text:'导出功能是否需要限制数据量？'},{role:'ai',text:'建议单次上限 50,000 条，超出后引导缩小筛选范围，并采用异步任务避免请求超时。'}])
const sections=[{id:'overview',label:'1. 项目概述'},{id:'roles',label:'2. 用户角色'},{id:'features',label:'3. 功能需求'},{id:'workflow',label:'4. 核心流程'},{id:'rules',label:'5. 业务规则'},{id:'nonfunctional',label:'6. 非功能需求'},{id:'acceptance',label:'7. 验收标准'}]
const project=computed(()=>app.projects.find(p=>p.id===route.params.id)||app.projects[0])
async function save(){try{const markdown=`# ${project.value.name}\n\n## 项目概述\n${project.value.description}\n\n## 核心能力\n- 请假申请与额度校验\n- 多级审批\n- 团队日历\n- Excel 报表导出\n\n## 验收标准\n- 核心功能测试覆盖率不低于 80%\n- 增量变更保持已有 API 兼容\n`;const result=await api.saveRequirement(projectId,{title:`${project.value.name}需求说明书`,contentMarkdown:markdown,structuredData:{summary:project.value.description},status:'confirmed',changeSummary:'用户编辑并确认'});persistedVersion.value=result.version;editing.value=false;app.toast('需求已持久化',`需求说明书 v${result.version} 已保存并同步至 Agent 上下文。`)}catch(error){app.toast('保存失败',error instanceof Error?error.message:'请稍后重试')}}
async function uploadAttachment(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;try{await api.uploadAttachment(projectId,file);app.toast('附件已上传',`${file.name} 已存储并提取可读文本。`)}catch(error){app.toast('上传失败',error instanceof Error?error.message:'请稍后重试')}}
onMounted(async()=>{try{const rows=await api.requirements(projectId);persistedVersion.value=rows[0]?.version||0}catch{}})
function send(){if(!question.value.trim())return;messages.value.push({role:'user',text:question.value},{role:'ai',text:'已记录该补充信息。若确认，我会将其更新到需求说明书并重新评估影响范围。'});question.value=''}
</script>

<template>
  <div class="content-width requirements-page">
    <PageTitle eyebrow="PROJECT REQUIREMENT" title="需求说明书" description="维护结构化项目需求，并与项目经理智能体持续澄清。">
      <button class="button secondary" @click="showHistory=!showHistory"><History :size="16"/>版本历史</button><button v-if="!editing" class="button primary" @click="editing=true"><Pencil :size="16"/>编辑需求</button><button v-else class="button primary" @click="save"><Save :size="16"/>保存变更</button>
    </PageTitle>
    <section class="requirement-statusbar"><div><StatusBadge status="completed" label="已确认"/><span>需求版本 <b>v{{persistedVersion||1}}</b></span><i></i><span><UserRound :size="13"/>最后编辑：林嘉</span><i></i><span><Clock3 :size="13"/>今天 09:28</span></div><div><span class="sync-state"><CheckCircle2 :size="14"/>已同步至智能体上下文</span><button class="icon-button"><MoreHorizontal :size="18"/></button></div></section>
    <div class="requirements-layout">
      <aside class="requirement-outline panel"><header><strong>文档目录</strong><button><Plus :size="15"/></button></header><nav><button v-for="item in sections" :key="item.id" :class="{active:activeSection===item.id}" @click="activeSection=item.id">{{item.label}}</button></nav><div class="requirement-files"><h4>参考附件 <span>3</span></h4><button><span><FileText :size="15"/></span><div><b>原始需求访谈.md</b><small>28 KB</small></div></button><button><span><File :size="15"/></span><div><b>审批流程图.pdf</b><small>1.8 MB</small></div></button><label class="upload-small"><Upload :size="14"/>上传附件<input type="file" accept=".pdf,.md,.txt,.json,.csv,.yaml,.yml" @change="uploadAttachment"/></label></div></aside>
      <main class="requirement-document panel" :class="{editing}">
        <header><div><span class="doc-type"><FileText :size="18"/></span><div><strong>{{project.name}} — 项目需求说明书</strong><small>REQ-LEAVE-HUB · v1.3.0</small></div></div><div class="doc-format"><button class="active">预览</button><button @click="editing=true">Markdown</button></div></header>
        <article :class="{editable:editing}" :contenteditable="editing">
          <section id="overview"><span class="section-number">01</span><h2>项目概述</h2><p>建设一套面向全体员工、部门负责人和人力资源团队的企业假勤管理平台，覆盖请假申请、多级审批、假期额度、团队日历及数据分析，减少线下沟通与重复统计成本。</p><div class="info-quote"><Sparkles :size="16"/><p><b>项目目标</b>员工可在 3 分钟内完成请假申请；审批人可集中处理待办；HR 可实时掌握全公司假勤趋势。</p></div></section>
          <section id="roles"><span class="section-number">02</span><h2>用户角色</h2><table><thead><tr><th>角色</th><th>职责与权限</th><th>使用频率</th></tr></thead><tbody><tr><td><b>普通员工</b></td><td>发起、撤回请假申请，查看额度与审批状态</td><td>每月</td></tr><tr><td><b>部门负责人</b></td><td>审批直属成员申请，查看团队假勤日历</td><td>每日</td></tr><tr><td><b>HR 管理员</b></td><td>配置假期、审批策略，导出统计报表</td><td>每周</td></tr></tbody></table></section>
          <section id="features"><span class="section-number">03</span><h2>核心功能需求</h2><div class="feature-requirements"><div><span>FR-01</span><p><b>请假申请</b>支持年假、病假、调休等类型，自动校验余额和日期冲突。</p><em>P0</em></div><div><span>FR-02</span><p><b>三级审批配置</b>按部门、假期类型和天数配置一至三级审批链。</p><em>P0</em></div><div><span>FR-03</span><p><b>团队假勤日历</b>按月查看权限范围内的团队请假分布。</p><em>P1</em></div><div class="changed"><span>FR-04</span><p><b>Excel 报表导出</b>按部门、日期、审批状态筛选后异步导出，单次上限 50,000 条。</p><em>新增</em></div></div></section>
          <section id="workflow"><span class="section-number">04</span><h2>核心业务流程</h2><div class="mini-flow"><div><span>1</span><b>填写申请</b></div><i></i><div><span>2</span><b>额度校验</b></div><i></i><div><span>3</span><b>多级审批</b></div><i></i><div><span>4</span><b>结果通知</b></div></div></section>
          <section id="acceptance"><span class="section-number">07</span><h2>关键验收标准</h2><ul class="acceptance-list"><li><Check :size="15"/>员工提交合法申请后，审批人在 5 秒内收到待办通知</li><li><Check :size="15"/>历史两级审批数据在升级后可正常查询且状态一致</li><li><Check :size="15"/>50,000 条假勤明细可在 2 分钟内完成导出</li><li><Check :size="15"/>核心功能自动化测试覆盖率不低于 80%</li></ul></section>
        </article>
      </main>
      <aside class="requirement-assistant panel">
        <header><div><span><Sparkles :size="17"/></span><div><strong>项目经理智能体</strong><small><i></i>在线 · 已加载项目上下文</small></div></div><button class="icon-button"><MoreHorizontal :size="17"/></button></header>
        <div class="requirement-score"><div><span>92</span><small>需求完整度</small></div><p><b>结构清晰，可以执行</b><small>已覆盖角色、流程、规则和验收标准</small></p></div>
        <div class="clarify-list"><h4>待确认项 <span>2</span></h4><button><AlertCircle :size="15"/><div><b>导出文件保留时长</b><small>建议确认临时文件清理策略</small></div></button><button><AlertCircle :size="15"/><div><b>审批超时处理</b><small>是否需要自动升级提醒？</small></div></button></div>
        <div class="assistant-chat"><div class="chat-scroll"><div v-for="(item,i) in messages" :key="i" :class="['mini-message',item.role]"><span v-if="item.role==='ai'">AI</span><p>{{item.text}}</p></div></div><div class="assistant-compose"><textarea v-model="question" placeholder="补充需求或向智能体提问…" @keydown.meta.enter="send"></textarea><div><button><Paperclip :size="14"/></button><button class="send-small" @click="send"><Send :size="14"/></button></div></div></div>
      </aside>
    </div>
    <div v-if="showHistory" class="side-drawer-backdrop" @click.self="showHistory=false"><aside class="side-drawer"><header><div><h3>需求版本历史</h3><p>共 5 个已保存版本</p></div><button class="icon-button" @click="showHistory=false"><X :size="18"/></button></header><div class="version-history"><article class="current"><span></span><div><b>v1.3.0 <em>当前</em></b><p>新增 Excel 报表导出需求与验收标准</p><small>林嘉 · 今天 09:28</small></div></article><article><span></span><div><b>v1.2.0</b><p>审批流程支持三级配置</p><small>赵玮 · 2026-08-12</small></div></article><article><span></span><div><b>v1.1.0</b><p>新增团队假勤日历</p><small>林嘉 · 2026-08-01</small></div></article><article><span></span><div><b>v1.0.0</b><p>首次确认项目需求</p><small>林嘉 · 2026-07-29</small></div></article></div></aside></div>
  </div>
</template>
