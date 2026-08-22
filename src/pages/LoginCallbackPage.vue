<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAppStore } from '../stores/app'
import { ArrowLeft, ArrowRight, Command, LoaderCircle, ShieldCheck, ShieldX } from 'lucide-vue-next'

const route=useRoute();const router=useRouter();const app=useAppStore()
const state=ref<'processing'|'success'|'error'>('processing')
const errorMessage=ref('')
const errorDetail=ref('')

onMounted(async()=>{
  const code=String(route.query.code||'');const oidcState=String(route.query.state||'')
  const idpError=String(route.query.error||'');const idpErrorDescription=String(route.query.error_description||'')
  if(idpError){state.value='error';errorMessage.value='企业身份认证被拒绝或失败';errorDetail.value=idpErrorDescription||idpError;return}
  if(!code||!oidcState){state.value='error';errorMessage.value='OIDC 回调参数缺失';errorDetail.value='身份提供商未返回授权码或 state 参数。';return}
  try{
    await api.oidcCallback(code,oidcState)
    await app.initAuth()
    state.value='success'
    window.setTimeout(()=>router.replace('/projects'),600)
  }catch(error){
    state.value='error'
    errorMessage.value=error instanceof Error?error.message:'OIDC 登录失败'
    errorDetail.value='授权码换取失败，可能是 state 过期、企业身份未配置邮箱或身份提供商暂时不可用。'
  }
})
</script>

<template>
  <div class="login-page oidc-callback-page">
    <section class="login-showcase">
      <div class="login-brand"><span><Command :size="22"/></span><div><strong>智构</strong><small>AGENT STUDIO</small></div></div>
      <div class="login-hero-copy"><span class="login-kicker">SSO · OIDC</span><h1>企业身份<br/><em>认证中</em></h1><p>正在通过企业身份提供商完成单点登录，请稍候。</p></div>
      <div class="login-orb orb-one"></div><div class="login-orb orb-two"></div><div class="login-grid-bg"></div>
    </section>
    <section class="login-form-side">
      <div class="login-form-card oidc-card">
        <div class="login-mobile-brand"><span><Command :size="20"/></span><strong>智构</strong></div>
        <template v-if="state==='processing'">
          <div class="oidc-icon processing"><LoaderCircle :size="26" class="spin"/></div>
          <span class="form-eyebrow">OIDC CALLBACK</span>
          <h2>正在完成登录</h2>
          <p class="login-subtitle">正在校验企业身份并换取访问凭据…</p>
        </template>
        <template v-else-if="state==='success'">
          <div class="oidc-icon success"><ShieldCheck :size="26"/></div>
          <span class="form-eyebrow">IDENTITY VERIFIED</span>
          <h2>认证成功</h2>
          <p class="login-subtitle">企业身份校验通过，正在进入工作空间…</p>
        </template>
        <template v-else>
          <div class="oidc-icon error"><ShieldX :size="26"/></div>
          <span class="form-eyebrow">AUTHENTICATION FAILED</span>
          <h2>单点登录失败</h2>
          <div class="login-error">{{errorMessage}}</div>
          <p class="login-subtitle">{{errorDetail}}</p>
          <button class="login-submit" @click="router.replace('/login')"><ArrowLeft :size="17"/><span>返回登录页</span></button>
          <button class="button ghost full-width" style="margin-top:10px" @click="router.replace('/login')"><span>使用账号密码登录</span><ArrowRight :size="16"/></button>
        </template>
      </div>
      <footer>© 2026 Agent Studio · 登录行为已记录至安全审计日志</footer>
    </section>
  </div>
</template>
