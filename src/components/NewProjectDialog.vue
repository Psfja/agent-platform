<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, Code2, LayoutTemplate, Server, Sparkles, X } from 'lucide-vue-next'
import { api } from '../api/client'
import { useAppStore } from '../stores/app'

const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const app = useAppStore()
const step = ref(1)
const name = ref('')
const description = ref('')
const template = ref('fullstack')
const generating = ref(false)
const llmReady = ref(false)
const autoBuild = ref(false)
const templates = [
  { id: 'fullstack', icon: LayoutTemplate, title: 'Web 全栈应用', text: '前端、后端、数据库与部署完整流程', tag: '推荐' },
  { id: 'api', icon: Server, title: 'API 后端服务', text: 'REST API、数据库、测试与容器部署', tag: '' },
  { id: 'frontend', icon: Code2, title: '前端应用', text: 'UI 设计、前端开发与自动化测试', tag: '' },
]
const canContinue = computed(() => name.value.trim().length > 1 && description.value.trim().length >= 10)

onMounted(async()=>{try{llmReady.value=(await api.agentBuildStatus()).configured}catch{llmReady.value=false}})

function next() {
  if (step.value === 1 && canContinue.value) step.value = 2
  else if (step.value === 2) step.value = 3
}
async function createProject() {
  generating.value = true
  try {
    const project = await app.createProject({
      name: name.value,
      description: description.value,
      template: templates.find(t => t.id === template.value)?.title || 'Web 全栈应用',
      autoBuild: autoBuild.value && llmReady.value && template.value === 'fullstack',
    })
    app.toast('项目已创建', autoBuild.value ? '真实 Agent 全栈构建已自动启动。' : '项目经理智能体正在生成需求说明书。')
    emit('close')
    router.push(autoBuild.value ? `/projects/${project.id}/build` : `/projects/${project.id}`)
  } catch {
    // Store 已统一展示后端错误。
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="modal-layer" @click.self="emit('close')">
    <section class="dialog project-dialog">
      <header class="dialog-head"><div><span class="dialog-kicker">CREATE PROJECT</span><h2>创建新项目</h2></div><button class="icon-button" @click="emit('close')"><X :size="19"/></button></header>
      <div class="stepper">
        <template v-for="(item, i) in ['描述需求','选择流程','确认启动']" :key="item">
          <div class="step-item" :class="{ active: step === i+1, done: step > i+1 }"><span><Check v-if="step > i+1" :size="13"/>{{ step <= i+1 ? i+1 : '' }}</span><b>{{ item }}</b></div>
          <i v-if="i<2" :class="{ done: step > i+1 }"></i>
        </template>
      </div>

      <div class="dialog-body">
        <div v-if="step === 1" class="dialog-section">
          <label class="form-label">项目名称 <em>*</em></label>
          <input class="form-input" v-model="name" placeholder="例如：员工培训管理系统" maxlength="40" autofocus/>
          <label class="form-label with-hint">告诉智能体你想构建什么 <em>*</em><span>{{ description.length }}/1000</span></label>
          <textarea class="form-textarea" v-model="description" placeholder="描述业务场景、核心功能和使用角色。例如：我需要一个员工培训管理系统，HR 可以发布课程，员工可以报名并查看学习进度…" maxlength="1000"></textarea>
          <div class="smart-tip"><Sparkles :size="17"/><div><b>描述得越具体，生成结果越准确</b><span>建议包含业务场景、用户角色、核心流程和关键数据。</span></div></div>
        </div>
        <div v-else-if="step === 2" class="dialog-section">
          <div class="recommendation"><Sparkles :size="16"/><span>根据需求，已为你推荐 <b>Web 全栈应用</b> 流程</span></div>
          <label class="template-option" v-for="item in templates" :key="item.id" :class="{ selected: template === item.id }">
            <input type="radio" v-model="template" :value="item.id"/><span class="template-icon"><component :is="item.icon" :size="21"/></span><div><strong>{{ item.title }} <em v-if="item.tag">{{ item.tag }}</em></strong><p>{{ item.text }}</p></div><i class="radio-ui"><Check :size="13"/></i>
          </label>
        </div>
        <div v-else class="dialog-section confirm-project">
          <div class="confirm-hero"><span><Sparkles :size="25"/></span><h3>一切就绪，可以开始了</h3><p>项目经理智能体将首先分析需求并生成结构化需求说明书，启动开发前仍会请你确认。</p></div>
          <dl class="confirm-list"><div><dt>项目名称</dt><dd>{{ name }}</dd></div><div><dt>流程模板</dt><dd>{{ templates.find(t => t.id === template)?.title }}</dd></div><div><dt>预计智能体</dt><dd>8 个专业角色</dd></div><div><dt>预计初版耗时</dt><dd>约 1.5 小时</dd></div></dl><label class="auto-build-option" :class="{disabled:!llmReady||template!=='fullstack'}"><input type="checkbox" v-model="autoBuild" :disabled="!llmReady||template!=='fullstack'"/><span><Check :size="13"/></span><div><b>创建后自动启动真实 Agent 全栈构建</b><small>{{!llmReady?'模型网关尚未配置，可稍后在 AI 构建页启动':template!=='fullstack'?'当前真实构建仅支持 Web 全栈模板':'自动完成代码生成、覆盖率、前端单测与生产构建'}}</small></div></label>
        </div>
      </div>
      <footer class="dialog-foot"><button class="button ghost" @click="step === 1 ? emit('close') : step--"><ArrowLeft v-if="step>1" :size="16"/>{{ step === 1 ? '取消' : '上一步' }}</button><button v-if="step<3" class="button primary" :disabled="step===1 && !canContinue" @click="next">继续<ArrowRight :size="16"/></button><button v-else class="button primary" :disabled="generating" @click="createProject"><span v-if="generating" class="spinner"></span><Sparkles v-else :size="16"/>{{ generating ? '正在初始化…' : '启动智能体团队' }}</button></footer>
    </section>
  </div>
</template>
