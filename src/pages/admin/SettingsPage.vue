<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Bell, Cloud, Database, Github, Globe2, Info, KeyRound, LockKeyhole, Mail, MessageSquare, RefreshCcw, Server, Settings, ShieldCheck, Sparkles, Workflow } from 'lucide-vue-next'
import { api, type SettingsStatus } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const app=useAppStore()
const tab=ref('models');const loading=ref(false);const errorMessage=ref('')
const status=ref<SettingsStatus|null>(null)
const llmDetail=ref<{configured:boolean;provider:string;model:string;message:string}|null>(null)
function yesNo(value:boolean){return value?'已配置':'未配置'}
function field(value:string|undefined|null,fallback='—'){return value||fallback}
async function load(){loading.value=true;errorMessage.value='';try{status.value=await api.settingsStatus();llmDetail.value=await api.agentBuildStatus().catch(()=>null)}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载平台配置'}finally{loading.value=false}}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page settings-page">
    <PageTitle eyebrow="PLATFORM ADMIN" title="系统设置" description="查看平台当前生效的模型网关、外部对接、通知与安全配置（只读状态）。">
      <button class="button secondary" @click="load"><RefreshCcw :size="16"/>{{loading?'加载中…':'刷新状态'}}</button>
    </PageTitle>
    <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
    <template v-else-if="status">
      <div class="smart-tip" style="margin-bottom:13px"><Info :size="16"/><div><b>配置为只读状态</b><span>平台配置通过后端 <code>backend/.env</code> 环境变量管理，修改后需重启 API 服务生效；密钥类配置不会在前端展示。</span></div></div>
      <div class="settings-layout">
        <aside class="settings-nav panel"><button v-for="item in [['models','模型网关',Sparkles],['git','Git 对接',Github],['notifications','通知渠道',Bell],['security','安全与 SSO',ShieldCheck],['general','通用配置',Settings]] as const" :key="item[0]" :class="{active:tab===item[0]}" @click="tab=item[0]"><component :is="item[2]" :size="17"/>{{item[1]}}</button></aside>
        <main>
          <section v-if="tab==='models'" class="panel settings-section">
            <div class="settings-section-head" style="padding:0 15px"><div><h3 style="margin:0">LLM 模型网关</h3><p style="margin:5px 0 0;color:var(--text-3);font-size:8px">DeepAgents 与生成应用通过 OpenAI 兼容网关调用模型</p></div><StatusBadge :status="status.llm.configured?'completed':'paused'" :label="status.llm.configured?'已配置':'未配置'"/></div>
            <div class="settings-form">
              <label><span>网关地址</span><code class="config-value">{{field(status.llm.baseUrl)}}</code></label>
              <label><span>默认模型</span><code class="config-value">{{field(status.llm.model)}}</code></label>
              <label><span>Agent 引擎</span><code class="config-value">{{status.llm.engine}}（{{status.llm.configured?'真实执行':'无 Key 时明确报错'}}）</code></label>
              <label><span>超时 / 重试</span><code class="config-value">{{status.llm.timeoutSeconds}}s / {{status.llm.maxRetries}} 次</code></label>
            </div>
            <div v-if="llmDetail" class="gateway-note"><Globe2 :size="15"/><span>{{llmDetail.message}}</span></div>
          </section>
          <section v-else-if="tab==='git'" class="panel settings-section">
            <div class="settings-section-head" style="padding:0 15px"><div><h3 style="margin:0">Git 代码仓库</h3><p style="margin:5px 0 0;color:var(--text-3);font-size:8px">生成应用源码提交与可选自动推送</p></div><StatusBadge :status="status.git.configured?'completed':'paused'" :label="status.git.configured?'已配置':'未配置'"/></div>
            <div class="settings-form">
              <label class="full"><span>远端仓库地址</span><code class="config-value">{{field(status.git.remote,'未配置（仅本地 Git 提交）')}}</code></label>
              <label><span>默认分支</span><code class="config-value">{{status.git.defaultBranch}}</code></label>
            </div>
          </section>
          <section v-else-if="tab==='notifications'" class="panel settings-section">
            <div class="settings-section-head" style="padding:0 15px"><div><h3 style="margin:0">通知渠道</h3><p style="margin:5px 0 0;color:var(--text-3);font-size:8px">站内通知始终可用，以下为外部渠道状态</p></div></div>
            <div class="settings-form">
              <label><span><Mail :size="13"/> 邮件（SMTP）</span><code class="config-value">{{yesNo(status.notifications.smtp.configured)}}{{status.notifications.smtp.host?` · ${status.notifications.smtp.host}:${status.notifications.smtp.port}`:''}}</code></label>
              <label><span><MessageSquare :size="13"/> Webhook</span><code class="config-value">{{yesNo(status.notifications.webhook.configured)}}</code></label>
            </div>
          </section>
          <section v-else-if="tab==='security'" class="panel settings-section">
            <div class="settings-section-head" style="padding:0 15px"><div><h3 style="margin:0">安全与单点登录</h3><p style="margin:5px 0 0;color:var(--text-3);font-size:8px">JWT、OIDC 与 LDAP 配置状态</p></div></div>
            <div class="settings-form">
              <label><span><KeyRound :size="13"/> JWT 算法</span><code class="config-value">{{status.security.jwtAlgorithm}}</code></label>
              <label><span>Access / Refresh 有效期</span><code class="config-value">{{status.security.accessTokenMinutes}} 分钟 / {{status.security.refreshTokenDays}} 天</code></label>
              <label><span><ShieldCheck :size="13"/> 企业 OIDC</span><code class="config-value">{{status.sso.oidc.configured?`已配置 · ${field(status.sso.oidc.issuer)}`:'未配置'}}</code></label>
              <label><span><LockKeyhole :size="13"/> LDAP</span><code class="config-value">{{status.sso.ldap.configured?`已配置 · ${field(status.sso.ldap.url)}`:'未配置'}}</code></label>
              <label class="full"><span>OIDC Client ID</span><code class="config-value">{{field(status.sso.oidc.clientId,'—')}}</code></label>
            </div>
          </section>
          <section v-else class="panel settings-section">
            <div class="settings-section-head" style="padding:0 15px"><div><h3 style="margin:0">通用配置</h3><p style="margin:5px 0 0;color:var(--text-3);font-size:8px">平台运行环境与存储信息</p></div></div>
            <div class="settings-form">
              <label><span>平台名称</span><code class="config-value">{{status.platform.name}}</code></label>
              <label><span>运行环境</span><code class="config-value">{{status.platform.environment}}（debug {{status.platform.debug?'开':'关'}}）</code></label>
              <label><span><Database :size="13"/> 主数据库</span><code class="config-value">{{status.database.engine}} · 自动迁移 {{status.database.migrationsEnabled?'开':'关'}}</code></label>
              <label><span><Cloud :size="13"/> 对象存储</span><code class="config-value">{{status.storage.minio.configured?`MinIO · ${field(status.storage.minio.endpoint)}/${field(status.storage.minio.bucket)}`:'本地文件降级'}}</code></label>
              <label><span><Workflow :size="13"/> 任务队列</span><code class="config-value">{{status.queue.redisAvailable?'Redis':'线程降级'}} · {{status.queue.queueName}}</code></label>
              <label><span><Server :size="13"/> 沙箱后端</span><code class="config-value">{{status.sandbox.activeBackend}}（{{status.sandbox.isolation}}）</code></label>
              <label><span>部署公网主机</span><code class="config-value">{{field(status.deployment.publicHost)}}</code></label>
              <label><span>生成应用数据库</span><code class="config-value">{{status.deployment.generatedDatabaseConfigured?'独立 Schema + 备份恢复':'未配置（应用内建存储）'}}</code></label>
              <label class="full"><span>状态生成时间</span><code class="config-value">{{new Date(status.generatedAt).toLocaleString('zh-CN',{hour12:false})}}</code></label>
            </div>
          </section>
        </main>
      </div>
    </template>
  </div>
</template>
