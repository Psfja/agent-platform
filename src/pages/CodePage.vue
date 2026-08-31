<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, ChevronRight, Clipboard, CloudDownload, Code2, FileCode2, FileJson, FileText, Folder, FolderOpen, GitBranch, History, Search, X } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { api, type AgentBuildRecord } from '../api/client'
import { useAppStore } from '../stores/app'
import PageTitle from '../components/PageTitle.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route=useRoute();const router=useRouter();const app=useAppStore()
const projectId=String(route.params.id)
const builds=ref<AgentBuildRecord[]>([]);const loading=ref(false);const errorMessage=ref('')
const selectedBuild=ref<AgentBuildRecord|null>(null)
const fileContent=ref<string|null>(null);const selectedPath=ref('');const loadingFile=ref(false)
const query=ref('');const expanded=ref<Record<string,boolean>>({});const copied=ref(false)

interface TreeNode { name:string; path:string; dir:boolean; children:TreeNode[] }
function buildTree(paths:string[]):TreeNode[]{
  const root:TreeNode[]=[]
  const index:Record<string,TreeNode>={}
  for(const path of paths){
    const parts=path.split('/');let current=root
    let prefix=''
    for(let i=0;i<parts.length;i++){
      const name=parts[i];const dir=i<parts.length-1
      prefix=prefix?`${prefix}/${name}`:name
      let node=current.find(n=>n.name===name&&n.dir===dir)
      if(!node){node={name,path:prefix,dir,children:[]};current.push(node);index[prefix]=node}
      current=node.children
    }
  }
  return root
}
const tree=computed(()=>selectedBuild.value?buildTree(selectedBuild.value.generatedFiles.map(f=>f.path)):[])
function matches(node:TreeNode):boolean{
  if(node.name.toLowerCase().includes(query.value.toLowerCase()))return true
  return node.children.some(matches)
}
function visible(root:TreeNode[]):TreeNode[]{
  const result:TreeNode[]=[]
  for(const node of root){if(matches(node))result.push(node)}
  return result
}
const fileCount=computed(()=>selectedBuild.value?.generatedFiles.length||0)
async function load(){
  loading.value=true;errorMessage.value=''
  try{
    builds.value=await api.agentBuilds(projectId)
    selectedBuild.value=builds.value.find(b=>b.generatedFiles?.length)||null
    if(selectedBuild.value){
      expanded.value={}
      if(tree.value.length)expanded.value[tree.value[0].path]=true
      if(tree.value[0]?.children[0])expanded.value[tree.value[0].children[0].path]=true
    }
  }catch(error){errorMessage.value=error instanceof Error?error.message:'无法加载构建记录'}
  finally{loading.value=false}
}
async function openFile(node:TreeNode){
  if(node.dir){expanded.value[node.path]=!expanded.value[node.path];return}
  if(!selectedBuild.value)return
  selectedPath.value=node.path;loadingFile.value=true;fileContent.value=null
  try{const result=await api.agentBuildFile(projectId,selectedBuild.value.id,node.path);fileContent.value=result.content??''}
  catch(error){app.toast('读取失败',error instanceof Error?error.message:'请稍后重试')}
  finally{loadingFile.value=false}
}
async function copy(){if(!fileContent.value)return;await navigator.clipboard?.writeText(fileContent.value);copied.value=true;window.setTimeout(()=>copied.value=false,1500)}
function download(){if(selectedBuild.value)window.location.assign(api.agentBuildDownloadUrl(projectId,selectedBuild.value.id))}
function fmtSize(bytes:number){return bytes>=1024?`${(bytes/1024).toFixed(1)} KB`:`${bytes} B`}
async function pickBuild(id:string){const build=builds.value.find(b=>b.id===id);if(!build)return;selectedBuild.value=build;selectedPath.value='';fileContent.value=null;expanded.value={};if(tree.value.length)expanded.value[tree.value[0].path]=true}
onMounted(load)
</script>

<template>
  <div class="code-page">
    <div class="content-width">
      <PageTitle title="代码仓库" description="在线浏览智能体真实生成的源码文件与构建记录。">
        <button class="button secondary" :disabled="!selectedBuild" @click="download"><CloudDownload :size="16"/>下载 ZIP</button>
        <button class="button primary" @click="router.push(`/projects/${projectId}/build`)"><Code2 :size="16"/>AI 全栈构建</button>
      </PageTitle>
      <div v-if="errorMessage" class="admin-empty"><p>{{errorMessage}}</p><button class="button secondary" @click="load">重试</button></div>
      <section v-else-if="selectedBuild" class="repo-summary">
        <div><span><Code2 :size="19"/></span><div><small>当前构建</small><strong>{{selectedBuild.mode==='incremental'?'增量':'初始'}}构建 · {{selectedBuild.model}}</strong></div></div>
        <select class="repo-branch-select" :value="selectedBuild.id" @change="pickBuild(($event.target as HTMLSelectElement).value)"><option v-for="build in builds" :key="build.id" :value="build.id">{{build.id.slice(0,8)}} · {{build.mode==='incremental'?'增量':'初始'}} · {{new Date(build.createdAt).toLocaleDateString('zh-CN')}}</option></select>
        <div class="commit-info"><History :size="15"/><code>{{selectedBuild.generatedFiles.length}} 个文件</code><span>{{selectedBuild.createdAt}}</span><small>覆盖率 {{selectedBuild.coverage??'—'}}%</small></div>
        <StatusBadge :status="selectedBuild.status"/>
      </section>
      <div v-else-if="!loading" class="admin-empty"><p>暂无生成源码 · 完成一次「AI 全栈构建」后即可在线浏览文件。</p><button class="button primary" @click="router.push(`/projects/${projectId}/build`)">前往构建</button></div>
    </div>
    <div v-if="selectedBuild" class="code-workspace">
      <aside class="repository-tree">
        <div class="repo-search"><Search :size="14"/><input v-model="query" placeholder="搜索文件"/></div>
        <div class="tree-root"><FolderOpen :size="15"/><b>{{fileCount}} 个文件</b></div>
        <div class="tree-list">
          <template v-for="node in visible(tree)" :key="node.path">
            <div class="tree-row level-0" @click="openFile(node)"><ChevronDown v-if="node.dir&&expanded[node.path]" :size="13"/><ChevronRight v-else-if="node.dir" :size="13"/><component :is="node.dir?Folder:node.name.endsWith('.md')||node.name.endsWith('.json')?FileJson:FileCode2" :size="15"/><span>{{node.name}}</span></div>
            <template v-if="node.dir&&expanded[node.path]">
              <template v-for="child in node.children" :key="child.path">
                <div class="tree-row level-1" @click="openFile(child)"><ChevronDown v-if="child.dir&&expanded[child.path]" :size="13"/><ChevronRight v-else-if="child.dir" :size="13"/><component :is="child.dir?Folder:child.name.endsWith('.md')?FileText:FileCode2" :size="15"/><span>{{child.name}}</span></div>
                <template v-if="child.dir&&expanded[child.path]"><div v-for="grand in child.children" :key="grand.path" class="tree-row level-2" :class="{active:selectedPath===grand.path}" @click="openFile(grand)"><component :is="grand.dir?Folder:FileCode2" :size="14"/><span>{{grand.name}}</span></div></template>
              </template>
            </template>
          </template>
        </div>
      </aside>
      <main class="code-editor-panel">
        <header><div class="editor-breadcrumb"><span>构建</span><ChevronRight :size="13"/><span>{{selectedBuild.id.slice(0,8)}}</span><template v-if="selectedPath"><ChevronRight :size="13"/><b>{{selectedPath.split('/').pop()}}</b></template></div><div><button :disabled="!fileContent" @click="copy"><Clipboard :size="14"/>{{copied?'已复制':'复制'}}</button><button @click="selectedPath='';fileContent=null"><X :size="15"/></button></div></header>
        <div v-if="loadingFile" class="code-editor"><div class="deployment-empty-row">正在读取文件…</div></div>
        <pre v-else-if="fileContent!==null" class="code-editor code-pre">{{fileContent}}</pre>
        <div v-else class="code-editor"><div class="deployment-empty-row">从左侧文件树选择文件查看内容</div></div>
        <footer v-if="selectedPath"><span>{{selectedPath.split('.').pop()?.toUpperCase()}}</span><span>UTF-8</span><span class="code-ok">{{selectedBuild.generatedFiles.find(f=>f.path===selectedPath)?.size?fmtSize(selectedBuild.generatedFiles.find(f=>f.path===selectedPath)!.size):''}}</span></footer>
      </main>
    </div>
  </div>
</template>
