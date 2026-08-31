<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, KeyRound, Mail, Search, ShieldCheck, Trash2, UserCheck, UserPlus, Users, X } from 'lucide-vue-next'
import { api, ApiError, type AdminUserRecord } from '../../api/client'
import { useAppStore } from '../../stores/app'
import PageTitle from '../../components/PageTitle.vue'

const app=useAppStore()
const users=ref<AdminUserRecord[]>([]);const loading=ref(false);const search=ref('');const errorMessage=ref('');const currentUser=ref<AdminUserRecord|null>(null)
const showAdd=ref(false);const adding=ref(false);const addError=ref('')
const pendingDelete=ref<AdminUserRecord|null>(null);const deleting=ref(false);const reassignProjects=ref(true)
const resetTarget=ref<AdminUserRecord|null>(null);const resetPassword=ref('');const resetting=ref(false);const resetError=ref('')
const draft=ref({email:'',displayName:'',department:'',platformRole:'user',initialPassword:''})
const ROLE_OPTIONS=[{value:'user',label:'普通用户'},{value:'platform_admin',label:'平台管理员'},{value:'super_admin',label:'超级管理员'}]
const ROLE_LABELS:{[key:string]:string}={super_admin:'超级管理员',platform_admin:'平台管理员',user:'普通用户'}
const ROLE_CLASS:{[key:string]:string}={super_admin:'owner',platform_admin:'manager',user:''}
const filtered=computed(()=>users.value.filter(u=>`${u.displayName}${u.email}${u.department}`.toLowerCase().includes(search.value.toLowerCase())))
const metrics=computed(()=>({total:users.value.length,active:users.value.filter(u=>u.isActive).length,admins:users.value.filter(u=>u.platformRole!=='user').length,projects:users.value.reduce((sum,u)=>sum+u.projectCount,0)}))
async function load(){loading.value=true;errorMessage.value='';try{const [list,me]=await Promise.all([api.adminUsers(),api.me().catch(()=>null)]);users.value=list;currentUser.value=list.find(u=>u.id===me?.id)||null}catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载平台用户'}finally{loading.value=false}}
async function changeRole(user:AdminUserRecord,role:string){if(role===user.platformRole)return;try{const updated=await api.updateAdminUser(user.id,{platformRole:role});replace(updated);app.toast('角色已更新',`${updated.displayName} 的角色已变更为${ROLE_LABELS[updated.platformRole]||updated.platformRole}。`)}catch(error){app.toast('更新失败',error instanceof Error?error.message:'角色变更可能需要超级管理员权限')}}
async function toggleActive(user:AdminUserRecord){try{const updated=await api.updateAdminUser(user.id,{isActive:!user.isActive});replace(updated);app.toast(updated.isActive?'账号已启用':'账号已停用',`${updated.displayName} 已${updated.isActive?'恢复访问':'被停用'}。`)}catch(error){app.toast('操作失败',error instanceof Error?error.message:'不能停用当前账号或受保护账号')}}
function replace(updated:AdminUserRecord){const index=users.value.findIndex(u=>u.id===updated.id);if(index>=0)users.value[index]=updated}
async function add(){
  adding.value=true;addError.value=''
  try{
    const result=await api.createAdminUser({email:draft.value.email.trim(),displayName:draft.value.displayName.trim(),department:draft.value.department.trim(),platformRole:draft.value.platformRole,initialPassword:draft.value.initialPassword||undefined})
    users.value.push(result.user);showAdd.value=false
    if(result.tempPassword)app.toast('用户已创建 · 初始密码',`${result.user.displayName} 的初始密码：${result.tempPassword}（仅本次显示，请妥善转交）`)
    else app.toast('用户已创建',`${result.user.displayName} 已加入平台。`)
  }catch(error){addError.value=error instanceof ApiError?error.message:error instanceof Error?error.message:'创建失败'}
  finally{adding.value=false}
}
async function remove(){if(!pendingDelete.value)return;deleting.value=true;try{const target=pendingDelete.value;await api.deleteAdminUser(target.id,reassignProjects.value);users.value=users.value.filter(u=>u.id!==target.id);app.toast('用户已删除',`${target.displayName} 已从平台移除${target.ownedProjects>0&&reassignProjects.value?`，其名下 ${target.ownedProjects} 个项目已移交给你`:''}。`);pendingDelete.value=null;reassignProjects.value=true}catch(error){app.toast('删除失败',error instanceof Error?error.message:'请确认项目移交或联系超级管理员')}finally{deleting.value=false}}
async function doReset(){if(!resetTarget.value)return;resetting.value=true;resetError.value='';try{const updated=await api.updateAdminUser(resetTarget.value.id,{newPassword:resetPassword.value});replace(updated);app.toast('密码已重置',`${updated.displayName} 的新密码已生效。`);resetTarget.value=null;resetPassword.value=''}catch(error){resetError.value=error instanceof Error?error.message:'重置失败'}finally{resetting.value=false}}
function lastLogin(item:AdminUserRecord):string{if(!item.lastLoginAt)return '从未登录';const minutes=Math.max(0,Math.floor((Date.now()-new Date(item.lastLoginAt).getTime())/60000));if(minutes<1)return '当前在线';if(minutes<60)return `${minutes} 分钟前`;if(minutes<1440)return `${Math.floor(minutes/60)} 小时前`;return `${Math.floor(minutes/1440)} 天前`}
onMounted(load)
</script>

<template>
  <div class="content-width admin-page users-page">
    <PageTitle eyebrow="SUPER ADMIN" title="用户与权限" description="管理平台用户、角色与账号状态；操作均写入审计日志。">
      <button class="button primary" @click="showAdd=true;addError='';draft={email:'',displayName:'',department:'',platformRole:'user',initialPassword:''}"><UserPlus :size="16"/>添加用户</button>
    </PageTitle>
    <div class="admin-metrics">
      <article><span class="metric-icon indigo"><Users :size="19"/></span><div><small>平台用户</small><strong>{{metrics.total}}</strong><em>已注册账号总数</em></div></article>
      <article><span class="metric-icon green"><UserCheck :size="19"/></span><div><small>正常状态</small><strong>{{metrics.active}}</strong><em>可登录平台</em></div></article>
      <article><span class="metric-icon blue"><ShieldCheck :size="19"/></span><div><small>管理员</small><strong>{{metrics.admins}}</strong><em>超管 + 平台管理员</em></div></article>
      <article><span class="metric-icon amber"><Mail :size="19"/></span><div><small>项目参与</small><strong>{{metrics.projects}}</strong><em>成员与所有关系合计</em></div></article>
    </div>
    <section class="panel user-table-panel">
      <header class="table-toolbar"><div class="inline-search admin-search"><Search :size="15"/><input v-model="search" placeholder="搜索姓名、邮箱或部门"/></div><div><button class="filter-button" @click="load">{{loading?'加载中…':'刷新'}}</button></div></header>
      <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
      <table v-else-if="loading" class="data-table user-table">
        <thead><tr><th>用户</th><th>部门</th><th>平台角色</th><th>账号来源</th><th>参与项目</th><th>最近登录</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="row in 6" :key="row">
            <td><div class="member-cell"><span class="skeleton skeleton-avatar"></span><div style="flex:1"><div class="skeleton skeleton-cell" style="width:72px"></div><div class="skeleton skeleton-cell" style="width:128px"></div></div></div></td>
            <td><div class="skeleton skeleton-cell" style="width:64px"></div></td>
            <td><span class="skeleton skeleton-chip"></span></td>
            <td><span class="skeleton skeleton-chip" style="width:48px"></span></td>
            <td><div class="skeleton skeleton-cell" style="width:32px"></div></td>
            <td><div class="skeleton skeleton-cell" style="width:56px"></div></td>
            <td><span class="skeleton skeleton-chip" style="width:40px"></span></td>
            <td></td>
          </tr>
        </tbody>
      </table>
      <table v-else class="data-table user-table">
        <thead><tr><th>用户</th><th>部门</th><th>平台角色</th><th>账号来源</th><th>参与项目</th><th>最近登录</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="user in filtered" :key="user.id">
            <td><div class="member-cell"><span class="member-avatar">{{user.displayName.slice(0,2).toUpperCase()}}<i v-if="user.lastLoginAt&&Date.now()-new Date(user.lastLoginAt).getTime()<5*60000"></i></span><div><b>{{user.displayName}}<em v-if="user.id===currentUser?.id">当前账号</em></b><small>{{user.email}}</small></div></div></td>
            <td>{{user.department||'—'}}</td>
            <td><select class="role-select" :class="ROLE_CLASS[user.platformRole]||''" :value="user.platformRole" :disabled="user.id===currentUser?.id" @change="changeRole(user,($event.target as HTMLSelectElement).value)"><option v-for="role in ROLE_OPTIONS" :key="role.value" :value="role.value">{{role.label}}</option></select></td>
            <td><span class="source-chip">{{user.authSource==='local'?'本地账号':user.authSource.toUpperCase()}}</span></td>
            <td><b>{{user.projectCount}}</b> 个</td>
            <td><span class="presence" :class="{online:user.lastLoginAt&&Date.now()-new Date(user.lastLoginAt).getTime()<5*60000}"><i></i>{{lastLogin(user)}}</span></td>
            <td><button class="toggle-control" :class="{on:user.isActive}" :disabled="user.id===currentUser?.id" @click="toggleActive(user)"><i></i></button></td>
            <td><div class="row-actions"><button class="button subtle" @click="resetTarget=user;resetPassword='';resetError=''"><KeyRound :size="13"/>重置密码</button><button class="button danger-ghost" :disabled="user.id===currentUser?.id||user.platformRole==='super_admin'" :title="user.id===currentUser?.id?'不能删除当前账号':user.platformRole==='super_admin'?'超级管理员受保护':'删除该用户'" @click="pendingDelete=user;reassignProjects=true"><Trash2 :size="14"/></button></div></td>
          </tr>
          <tr v-if="!loading && !filtered.length"><td colspan="8" class="deployment-empty-row">没有匹配的用户</td></tr>
        </tbody>
      </table>
    </section>
    <div v-if="showAdd" class="modal-layer" @click.self="showAdd=false">
      <section class="dialog user-dialog">
        <header class="dialog-head"><div><span class="dialog-kicker">ADD PLATFORM USER</span><h2>添加平台用户</h2></div><button class="icon-button" @click="showAdd=false"><X :size="18"/></button></header>
        <div class="dialog-body">
          <div v-if="addError" class="login-error">{{addError}}</div>
          <label class="form-label">企业邮箱<em> *</em></label>
          <div class="form-input" style="display:flex;align-items:center;gap:7px"><Mail :size="15"/><input v-model="draft.email" type="email" placeholder="name@company.com" style="border:0;outline:0;flex:1;min-width:0;font-size:10px;color:var(--text)"/></div>
          <label class="form-label with-hint">显示姓名<em> *</em></label>
          <input class="form-input" v-model="draft.displayName" placeholder="张三"/>
          <label class="form-label">部门</label>
          <input class="form-input" v-model="draft.department" placeholder="信息技术部"/>
          <label class="form-label">平台角色</label>
          <div class="role-options compact"><label v-for="role in ROLE_OPTIONS" :key="role.value" :class="{selected:draft.platformRole===role.value}"><input type="radio" :checked="draft.platformRole===role.value" @change="draft.platformRole=role.value"/><span><Check :size="13"/></span><div><b>{{role.label}}</b></div></label></div>
          <label class="form-label with-hint">初始密码<span>留空则由系统生成，并在创建成功后一次性显示</span></label>
          <input class="form-input" v-model="draft.initialPassword" type="password" placeholder="至少 8 位" autocomplete="new-password"/>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">创建与后续变更均记录审计日志</span><div style="display:flex;gap:8px"><button class="button ghost" @click="showAdd=false">取消</button><button class="button primary" :disabled="adding" @click="add"><UserPlus :size="16"/>{{adding?'创建中…':'创建用户'}}</button></div></footer>
      </section>
    </div>
    <div v-if="pendingDelete" class="modal-layer" @click.self="pendingDelete=null">
      <section class="dialog" style="width:min(460px,calc(100vw - 50px))">
        <header class="dialog-head"><div><span class="dialog-kicker">DELETE USER</span><h2>删除平台用户</h2></div><button class="icon-button" @click="pendingDelete=null"><X :size="18"/></button></header>
        <div class="dialog-body">
          <p class="dialog-text">确定删除 <b>{{pendingDelete.displayName}}</b>（{{pendingDelete.email}}）吗？此操作不可撤销。</p>
          <label v-if="pendingDelete.ownedProjects>0" class="reassign-option"><input type="checkbox" v-model="reassignProjects"/><span><Check :size="12"/></span><div><b>将其名下 {{pendingDelete.ownedProjects}} 个项目移交给我</b><small>不勾选则无法删除仍拥有项目的用户</small></div></label>
          <div v-else class="smart-tip"><ShieldCheck :size="15"/><div><b>该用户未拥有项目</b><span>删除后其项目成员关系一并解除。</span></div></div>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">删除与移交均写入审计日志</span><div style="display:flex;gap:8px"><button class="button ghost" @click="pendingDelete=null">取消</button><button class="button danger-ghost" :disabled="deleting||(pendingDelete.ownedProjects>0&&!reassignProjects)" @click="remove"><Trash2 :size="15"/>{{deleting?'删除中…':'确认删除'}}</button></div></footer>
      </section>
    </div>
    <div v-if="resetTarget" class="modal-layer" @click.self="resetTarget=null">
      <section class="dialog" style="width:min(430px,calc(100vw - 50px))">
        <header class="dialog-head"><div><span class="dialog-kicker">RESET PASSWORD</span><h2>重置密码</h2></div><button class="icon-button" @click="resetTarget=null"><X :size="18"/></button></header>
        <div class="dialog-body">
          <div v-if="resetError" class="login-error">{{resetError}}</div>
          <p class="dialog-text">为 <b>{{resetTarget.displayName}}</b>（{{resetTarget.email}}）设置新密码：</p>
          <input class="form-input" v-model="resetPassword" type="password" placeholder="至少 8 位" autocomplete="new-password"/>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">重置后用户需使用新密码登录</span><div style="display:flex;gap:8px"><button class="button ghost" @click="resetTarget=null">取消</button><button class="button primary" :disabled="resetting||resetPassword.length<8" @click="doReset"><KeyRound :size="15"/>{{resetting?'重置中…':'确认重置'}}</button></div></footer>
      </section>
    </div>
  </div>
</template>
