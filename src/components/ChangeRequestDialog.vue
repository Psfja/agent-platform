<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlertTriangle, ArrowLeft, Check, CheckCircle2, Database, FileCode2, GitBranch, LoaderCircle, ShieldCheck, Sparkles, X } from 'lucide-vue-next'
import { api, type ImpactAnalysisResult } from '../api/client'
import { useAppStore } from '../stores/app'

const emit = defineEmits<{ close: []; submitted: [] }>()
const app = useAppStore(); const route=useRoute(); const projectId=String(route.params.id || 'leave-hub')
const project=computed(()=>app.projects.find(item=>item.id===projectId) || app.projects[0])
const step = ref(1)
const request = ref('新增假勤报表导出功能，支持按部门、日期和审批状态筛选，并导出为 Excel 文件。导出数据量较大时需要显示处理进度。')
const analyzing = ref(false); const confirmed = ref(false); const analysis=ref<ImpactAnalysisResult | null>(null)
const canAnalyze = computed(() => request.value.trim().length >= 20)
const riskLabel=computed(()=>analysis.value?.riskLevel==='high'?'高':analysis.value?.riskLevel==='medium'?'中':'低')
const initials:Record<string,string>={'架构设计':'AR','后端开发':'BE','前端开发':'FE','数据库设计':'DB','代码审查':'CR','测试工程师':'QA'}
async function analyze() {
  analyzing.value = true
  try{analysis.value=await api.analyze(projectId,request.value);step.value=2}catch(error){app.toast('分析失败',error instanceof Error?error.message:'请稍后重试')}finally{analyzing.value=false}
}
async function submit() {
  if(!analysis.value)return;confirmed.value=true
  try{await api.confirmIteration(projectId,analysis.value.iterationId);await app.loadProjects();app.toast('迭代已启动', `${analysis.value.proposedVersion} 增量任务已加入执行队列。`);emit('submitted');emit('close')}catch(error){app.toast('启动失败',error instanceof Error?error.message:'请稍后重试');confirmed.value=false}
}
</script>

<template>
  <div class="modal-layer" @click.self="emit('close')">
    <section class="dialog change-dialog">
      <header class="dialog-head"><div><span class="dialog-kicker">INCREMENTAL ITERATION</span><h2>提出新需求</h2></div><button class="icon-button" @click="emit('close')"><X :size="19"/></button></header>
      <div class="change-stepbar"><div :class="{active:step===1,done:step>1}"><span>1</span>描述变更</div><i></i><div :class="{active:step===2}"><span>2</span>影响分析</div></div>
      <div class="dialog-body">
        <div v-if="step===1" class="dialog-section">
          <div class="context-card"><GitBranch :size="18"/><div><span>基于当前项目</span><strong>{{project?.version}} · {{project?.status==='completed'?'已完成':'运行中'}}</strong></div><small>{{project?.name}}</small></div>
          <label class="form-label with-hint">描述这次要改变什么 <em>*</em><span>{{ request.length }}/1000</span></label>
          <textarea class="form-textarea change-textarea" v-model="request" maxlength="1000"></textarea>
          <div class="suggestion-chips"><span>快捷补充</span><button @click="request += ' 不影响现有审批流程。'">保持向后兼容</button><button @click="request += ' 仅管理员可以操作。'">增加权限要求</button><button @click="request += ' 需要记录操作日志。'">增加审计日志</button></div>
          <div class="smart-tip"><Sparkles :size="17"/><div><b>不会推倒重来</b><span>平台会先分析代码、Schema 和 API，只激活受影响的智能体并最小化修改。</span></div></div>
        </div>
        <div v-else class="dialog-section impact-report">
          <div class="report-summary"><div class="report-score"><span>低</span><small>变更风险</small></div><div><span class="success-title"><CheckCircle2 :size="18"/>影响分析完成</span><p>本次为功能级增量变更，无破坏性 API 或数据库结构调整，可以安全执行。</p></div></div>
          <div class="impact-metrics">
            <div><span class="metric-icon indigo"><FileCode2 :size="18"/></span><p><small>受影响模块</small><strong>3 <em>个</em></strong></p></div>
            <div><span class="metric-icon blue"><GitBranch :size="18"/></span><p><small>预估改动文件</small><strong>8–12 <em>个</em></strong></p></div>
            <div><span class="metric-icon green"><Database :size="18"/></span><p><small>数据库变更</small><strong class="safe-text">无</strong></p></div>
            <div><span class="metric-icon amber"><ShieldCheck :size="18"/></span><p><small>已有 API 影响</small><strong class="safe-text">无</strong></p></div>
          </div>
          <div class="impact-columns">
            <section><h4>受影响范围</h4><ul><li><span>后端 · 报表服务</span><b>新增接口</b></li><li><span>前端 · 假勤报表</span><b>新增交互</b></li><li><span>权限 · 数据导出</span><b>复用规则</b></li></ul></section>
            <section><h4>计划激活智能体</h4><div class="agent-pills"><span><i>BE</i>后端开发</span><span><i>FE</i>前端开发</span><span><i>CR</i>代码审查</span><span><i>QA</i>测试工程师</span></div></section>
          </div>
          <div class="warning-box"><AlertTriangle :size="17"/><div><b>需关注大数据量导出</b><span>建议采用异步任务，限制单次导出上限为 50,000 条；已加入增量方案。</span></div></div>
        </div>
      </div>
      <footer class="dialog-foot"><button class="button ghost" @click="step===1 ? emit('close') : step=1"><ArrowLeft v-if="step>1" :size="16"/>{{ step===1 ? '取消' : '调整需求' }}</button><button v-if="step===1" class="button primary" :disabled="!canAnalyze || analyzing" @click="analyze"><LoaderCircle v-if="analyzing" :size="16" class="spin"/><Sparkles v-else :size="16"/>{{ analyzing ? '智能体正在分析…' : '生成影响分析' }}</button><button v-else class="button primary" :disabled="confirmed" @click="submit"><span v-if="confirmed" class="spinner"></span><Check v-else :size="16"/>{{ confirmed ? '正在启动…' : '确认并开始迭代' }}</button></footer>
    </section>
  </div>
</template>
