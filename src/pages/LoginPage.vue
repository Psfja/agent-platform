<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAppStore } from '../stores/app'
import { ArrowRight, CheckCircle2, Command, Eye, EyeOff, Fingerprint, KeyRound, LoaderCircle, LockKeyhole, Network, ShieldCheck, Sparkles, Workflow } from 'lucide-vue-next'

const router=useRouter();const route=useRoute();const app=useAppStore();const sso=ref({oidcConfigured:false,ldapConfigured:false});const account=ref('admin@company.com');const password=ref('Admin@2026');const showPassword=ref(false);const remember=ref(true);const loading=ref(false);const errorMessage=ref('')
async function login(){loading.value=true;errorMessage.value='';try{await api.login(account.value,password.value);await app.initAuth();router.push(String(route.query.redirect||'/projects'))}catch(error){errorMessage.value=error instanceof Error?error.message:'登录失败，请重试'}finally{loading.value=false}}
async function startOIDC(){try{const result=await api.oidcStart();window.location.assign(result.authorizationUrl)}catch(error){errorMessage.value=error instanceof Error?error.message:'OIDC 未配置'}}
async function loginLDAP(){loading.value=true;try{await api.ldapLogin(account.value,password.value);await app.initAuth();router.push(String(route.query.redirect||'/projects'))}catch(error){errorMessage.value=error instanceof Error?error.message:'LDAP 登录失败'}finally{loading.value=false}}
onMounted(async()=>{try{sso.value=await api.ssoStatus()}catch{}})
</script>

<template>
  <div class="login-page">
    <section class="login-showcase">
      <div class="login-brand"><span><Command :size="22"/></span><div><strong>智构</strong><small>AGENT STUDIO</small></div></div>
      <div class="login-hero-copy"><span class="login-kicker"><Sparkles :size="14"/>企业智能体研发平台</span><h1>你的专属<br/><em>AI 软件工程团队</em></h1><p>从一句需求开始，由多智能体协作完成分析、设计、编码、测试、部署与持续迭代。</p><div class="login-features"><div><span><Network :size="18"/></span><div><b>多智能体协作</b><small>专业角色分工，任务透明可控</small></div></div><div><span><Workflow :size="18"/></span><div><b>全生命周期交付</b><small>需求到部署，一站式自动完成</small></div></div><div><span><ShieldCheck :size="18"/></span><div><b>企业级安全</b><small>私有化部署与项目数据隔离</small></div></div></div></div>
      <div class="login-proof"><div class="proof-avatars"><span>PM</span><span>AR</span><span>FE</span><span>BE</span><span>QA</span></div><p><strong>8 个专业智能体</strong><br/>随时为你的项目待命</p></div>
      <div class="login-orb orb-one"></div><div class="login-orb orb-two"></div><div class="login-grid-bg"></div>
    </section>
    <section class="login-form-side">
      <div class="login-form-card">
        <div class="login-mobile-brand"><span><Command :size="20"/></span><strong>智构</strong></div>
        <span class="form-eyebrow">WELCOME BACK</span><h2>欢迎回来</h2><p class="login-subtitle">登录企业工作空间，继续你的智能体项目。</p>
        <form @submit.prevent="login">
          <div v-if="errorMessage" class="login-error">{{errorMessage}}</div>
          <label>企业账号</label><div class="login-input"><Fingerprint :size="17"/><input v-model="account" type="email" placeholder="name@company.com"/></div>
          <div class="password-label"><label>密码</label><button type="button">忘记密码？</button></div><div class="login-input"><KeyRound :size="17"/><input v-model="password" :type="showPassword?'text':'password'" placeholder="输入密码"/><button type="button" @click="showPassword=!showPassword"><EyeOff v-if="showPassword" :size="16"/><Eye v-else :size="16"/></button></div>
          <label class="remember-row"><input type="checkbox" v-model="remember"/><i><CheckCircle2 :size="13"/></i><span>在此设备上保持登录</span></label>
          <button class="login-submit" type="submit" :disabled="loading"><LoaderCircle v-if="loading" :size="17" class="spin"/><span>{{loading?'正在验证身份…':'登录工作空间'}}</span><ArrowRight v-if="!loading" :size="17"/></button>
        </form>
        <div class="login-divider"><span>或使用企业身份认证</span></div>
        <div class="sso-buttons"><button :disabled="!sso.oidcConfigured" @click="startOIDC"><span class="sso-icon wecom">SSO</span>{{sso.oidcConfigured?'企业 OIDC':'OIDC 未配置'}}</button><button :disabled="!sso.ldapConfigured" @click="loginLDAP"><span class="sso-icon ldap"><LockKeyhole :size="15"/></span>{{sso.ldapConfigured?'LDAP 登录':'LDAP 未配置'}}</button></div>
        <div class="login-security"><ShieldCheck :size="15"/><span>连接受 TLS 加密保护，登录行为将记录至安全审计日志</span></div>
      </div>
      <footer>© 2026 Agent Studio · 隐私政策 · 使用条款</footer>
    </section>
  </div>
</template>
