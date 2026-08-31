<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { Bot, BrainCircuit, CircleHelp, FolderOpen, LoaderCircle, MessageSquarePlus, Send, ShieldCheck, Sparkles, Trash2, UserRound, Wand2, Wrench, X } from 'lucide-vue-next'
import { api, ApiError, type AgentTypeRecord, type ChatTurnRecord, type ConversationInterruptRecord, type ConversationMessageRecord, type ConversationRecord } from '../api/client'
import { useAppStore } from '../stores/app'

const props = defineProps<{ projectId: string }>()
const app = useAppStore()
const conversations = ref<ConversationRecord[]>([])
const agents = ref<AgentTypeRecord[]>([])
const currentId = ref('')
const messages = ref<ConversationMessageRecord[]>([])
const loading = ref(false); const sending = ref(false)
const input = ref(''); const remember = ref(true)
const errorMessage = ref(''); const lastTurn = ref<ChatTurnRecord|null>(null)
const streamingContent = ref(''); const streamContext = ref<ChatTurnRecord['context']|null>(null)
const renaming = ref(false)
const pendingInterrupt = ref<ConversationInterruptRecord|null>(null)
const deciding = ref(false); const decideError = ref('')
const editMode = ref(false); const editReason = ref(''); const editAction = ref('')
const showWorkspace = ref(false); const workspaceFiles = ref<{path:string;size:number}[]>([]); const workspaceLoading = ref(false)
const messagesEl = ref<HTMLElement|null>(null)

const currentConversation = computed(() => conversations.value.find(c => c.id === currentId.value) || null)
const agentLabel = (key: string) => { const a = agents.value.find(item => item.name === key); return a ? a.displayName : key }

async function loadAgents() { try { agents.value = await api.agentTypes() } catch { agents.value = [] } }
async function loadConversations(agentKey?: string) {
  try { conversations.value = await api.conversations(props.projectId, agentKey) } catch (error) { app.toast('加载失败', error instanceof Error ? error.message : '无法加载对话列表') }
}
async function openConversation(id: string) {
  currentId.value = id; loading.value = true; errorMessage.value = ''
  try {
    const [detail, interrupts] = await Promise.all([
      api.conversation(props.projectId, id),
      api.conversationInterrupts(props.projectId, id).catch(() => []),
    ])
    messages.value = detail.messages
    lastTurn.value = null
    pendingInterrupt.value = interrupts[0] || null
    editMode.value = false
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '无法加载对话' }
  finally { loading.value = false; await scrollBottom() }
}
async function newConversation() {
  const agentKey = agents.value.find(a => a.isActive)?.name || agents.value[0]?.name
  if (!agentKey) { app.toast('无可用智能体', '请先在智能体管理页启用智能体类型。'); return }
  try {
    const created = await api.createConversation(props.projectId, agentKey)
    conversations.value.unshift(created)
    await openConversation(created.id)
  } catch (error) { app.toast('创建失败', error instanceof Error ? error.message : '请稍后重试') }
}
async function removeConversation(item: ConversationRecord) {
  try {
    await api.deleteConversation(props.projectId, item.id)
    conversations.value = conversations.value.filter(c => c.id !== item.id)
    if (currentId.value === item.id) { currentId.value = ''; messages.value = [] }
    app.toast('对话已删除', '该对话及其消息已移除，提取的长期记忆保留。')
  } catch (error) { app.toast('删除失败', error instanceof Error ? error.message : '请稍后重试') }
}
async function scrollBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}
function updateConversationInList(record: ConversationRecord) {
  const index = conversations.value.findIndex(c => c.id === record.id)
  if (index >= 0) conversations.value[index] = record
}
function showError(error: unknown) {
  errorMessage.value = error instanceof ApiError
    ? `${error.message}${error.status === 503 ? '：请在 backend/.env 配置 LLM_API_KEY 后重启 API，对话能力需要真实模型，不会返回模拟回复。' : ''}`
    : error instanceof Error ? error.message : '发送失败'
}
async function send() {
  const content = input.value.trim()
  if (!content || !currentId.value || sending.value) return
  const localUser: ConversationMessageRecord = { id: `local-${Date.now()}`, role: 'user', content, metadata: {}, createdAt: new Date().toISOString() }
  messages.value.push(localUser)
  input.value = ''
  sending.value = true; errorMessage.value = ''
  streamingContent.value = ''; streamContext.value = null
  await scrollBottom()
  const finishWith = (assistant: ConversationMessageRecord) => {
    streamingContent.value = ''
    messages.value.push(assistant)
  }
  try {
    const done = await api.streamConversationMessage(props.projectId, currentId.value, content, remember.value, {
      onMeta: (context) => { streamContext.value = context as unknown as ChatTurnRecord['context']; scrollBottom() },
      onDelta: (chunk) => { streamingContent.value += chunk; scrollBottom() },
      onTitle: (title) => { updateConversationInList({ ...(conversations.value.find(c => c.id === currentId.value) as ConversationRecord), title }) },
      onInterrupt: (interrupt) => {
        pendingInterrupt.value = { id: interrupt.interruptId || 'pending', conversationId: currentId.value, toolName: interrupt.toolName, payload: interrupt.payload, status: 'pending', createdAt: new Date().toISOString() }
        scrollBottom()
      },
    })
    if (done.title) updateConversationInList({ ...(conversations.value.find(c => c.id === currentId.value) as ConversationRecord), title: done.title })
    updateConversationInList(done.conversation)
    if (done.assistantMessage) {
      lastTurn.value = {
        conversation: done.conversation,
        userMessage: localUser,
        assistantMessage: done.assistantMessage,
        memoriesUsed: done.memoriesUsed,
        context: streamContext.value || { historyMessages: 0, droppedMessages: 0, estimatedTokens: 0, budgetTokens: 0, memoriesRecalled: 0, skillsLoaded: 0 },
      }
      finishWith(done.assistantMessage)
    } else if (streamingContent.value) {
      // Agent 流式内容已显示，若 done 无消息则补一条本地记录
      const localAssistant: ConversationMessageRecord = { id: `local-a-${Date.now()}`, role: 'assistant', content: streamingContent.value, metadata: {}, createdAt: new Date().toISOString() }
      finishWith(localAssistant)
    }
    streamContext.value = null
  } catch (error) {
    streamingContent.value = ''
    if (error instanceof ApiError) {
      showError(error)
    } else {
      // 流式传输本身不可用（网络/浏览器限制）时降级为普通请求
      try {
        const turn = await api.sendConversationMessage(props.projectId, currentId.value, content, remember.value)
        lastTurn.value = turn
        updateConversationInList(turn.conversation)
        streamContext.value = null
        finishWith(turn.assistantMessage)
      } catch (fallbackError) { showError(fallbackError) }
    }
  } finally { sending.value = false; await scrollBottom() }
}
async function switchMode(mode: 'chat' | 'agent') {
  if (!currentId.value) return
  try {
    const updated = await api.setConversationMode(props.projectId, currentId.value, mode)
    updateConversationInList(updated)
    app.toast(mode === 'agent' ? '已切换工具模式' : '已切换聊天模式', mode === 'agent' ? '智能体现在拥有文件工作区、Python 沙箱与子智能体委派能力。' : '智能体现在进行纯对话回复。')
  } catch (error) { app.toast('切换失败', error instanceof Error ? error.message : '请稍后重试') }
}
async function decideInterrupt(decision: 'approve' | 'edit' | 'reject') {
  const interrupt = pendingInterrupt.value
  if (!interrupt || deciding.value) return
  deciding.value = true; decideError.value = ''
  try {
    const result = await api.decideConversationInterrupt(props.projectId, currentId.value, interrupt.id, decision, editReason.value, editAction.value ? JSON.parse(editAction.value || '{}') : {})
    updateConversationInList(result.conversation)
    messages.value.push(result.assistantMessage)
    pendingInterrupt.value = null
    editMode.value = false
    app.toast(decision === 'approve' ? '已批准' : decision === 'edit' ? '已修改批准' : '已驳回', '智能体已从检查点恢复并继续执行。')
    await scrollBottom()
  } catch (error) {
    if (error instanceof SyntaxError) decideError.value = '修改内容的 JSON 格式不正确'
    else decideError.value = error instanceof ApiError ? error.message : error instanceof Error ? error.message : '审批提交失败'
  } finally { deciding.value = false }
}
async function loadWorkspace() {
  if (!currentId.value) return
  showWorkspace.value = true; workspaceLoading.value = true
  try {
    const result = await api.conversationWorkspace(props.projectId, currentId.value)
    workspaceFiles.value = result.files
  } catch (error) { app.toast('加载失败', error instanceof Error ? error.message : '无法读取工作区') }
  finally { workspaceLoading.value = false }
}
function fmtFileSize(bytes:number){return bytes>=1024?`${(bytes/1024).toFixed(1)} KB`:`${bytes} B`}

async function regenerateTitle() {
  if (!currentId.value || renaming.value) return
  renaming.value = true
  try {
    const updated = await api.regenerateConversationTitle(props.projectId, currentId.value)
    updateConversationInList(updated)
    app.toast('标题已更新', `模型为会话生成了新标题：${updated.title}`)
  } catch (error) {
    app.toast('标题生成失败', error instanceof ApiError
      ? `${error.message}${error.status === 503 ? '（需要配置 LLM_API_KEY）' : ''}`
      : error instanceof Error ? error.message : '请稍后重试')
  } finally { renaming.value = false }
}
function formatTime(iso: string) { return new Date(iso).toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }

onMounted(async () => {
  await Promise.all([loadAgents(), loadConversations()])
  if (!currentId.value && conversations.value.length) await openConversation(conversations.value[0].id)
})
</script>

<template>
  <div class="conversation-layout">
    <aside class="panel conversation-sidebar">
      <header class="panel-title"><div><h3>会话列表</h3><p>{{conversations.length}} 个对话 · 长期记忆自动积累</p></div></header>
      <button class="new-chat-button" @click="newConversation"><MessageSquarePlus :size="15"/>新建对话</button>
      <div class="conversation-list">
        <button v-for="item in conversations" :key="item.id" :class="{ active: item.id === currentId }" @click="openConversation(item.id)">
          <span class="conversation-agent">{{ agentLabel(item.agentKey).slice(0, 2) }}</span>
          <div><b>{{ item.title }}</b><small>{{ agentLabel(item.agentKey) }} · {{ item.messageCount }} 条 · {{ formatTime(item.updatedAt) }}</small></div>
          <span class="conversation-delete" title="删除对话" @click.stop="removeConversation(item)"><Trash2 :size="13" /></span>
        </button>
        <div v-if="!conversations.length" class="conversation-empty"><Bot :size="22" /><p>还没有对话。新建一个对话，与该智能体讨论需求、方案或任何项目问题。</p></div>
      </div>
    </aside>

    <main class="panel conversation-main">
      <template v-if="currentId">
        <header class="conversation-head">
          <div><span class="conversation-agent big">{{ agentLabel(currentConversation?.agentKey || '').slice(0, 2) }}</span><div class="conversation-title-row"><h3>{{ currentConversation?.title || '对话' }}</h3><button class="title-wand" :disabled="renaming" title="AI 重新生成标题" @click="regenerateTitle"><LoaderCircle v-if="renaming" :size="13" class="spin"/><Wand2 v-else :size="13"/></button><p>{{ agentLabel(currentConversation?.agentKey || '') }} · 上下文窗口含长期记忆与 Skills 指令</p></div></div>
          <div class="conversation-head-actions">
            <button class="workspace-button" title="查看智能体工作区文件" @click="loadWorkspace"><FolderOpen :size="14"/>工作区</button>
            <div class="mode-switch" title="聊天模式=纯对话；工具模式=DeepAgents（文件工作区/沙箱/子智能体/审批）">
              <button :class="{ active: (currentConversation?.mode || 'chat') === 'chat' }" @click="switchMode('chat')">聊天</button>
              <button :class="{ active: (currentConversation?.mode || 'chat') === 'agent' }" @click="switchMode('agent')"><Wrench :size="11"/>工具</button>
            </div>
            <label class="remember-toggle" title="开启后每轮对话自动提取值得记住的事实写入长期记忆"><input type="checkbox" v-model="remember" /><i></i><span><BrainCircuit :size="13"/>记忆</span></label>
          </div>
        </header>
        <div ref="messagesEl" class="conversation-messages">
          <div v-for="message in messages" :key="message.id" class="chat-message" :class="message.role">
            <span class="chat-avatar"><UserRound v-if="message.role === 'user'" :size="15" /><Bot v-else :size="15" /></span>
            <div><div class="chat-bubble">{{ message.content }}</div><small>{{ formatTime(message.createdAt) }}</small></div>
          </div>
          <div v-if="sending" class="chat-message assistant">
            <span class="chat-avatar"><Bot :size="15" /></span>
            <div>
              <div v-if="streamingContent" class="chat-bubble">{{ streamingContent }}<i class="chat-cursor"></i></div>
              <div v-else class="chat-bubble typing"><LoaderCircle :size="14" class="spin" /> 正在结合长期记忆与上下文思考…</div>
            </div>
          </div>
          <div v-if="!loading && !messages.length && !sending" class="conversation-empty big"><Sparkles :size="26" /><p>开始和这个智能体对话吧。它会召回项目的长期记忆、加载已装配的 Skills，并在上下文窗口内延续讨论。</p></div>
        </div>
        <div v-if="pendingInterrupt" class="conversation-interrupt">
          <header><span><ShieldCheck :size="16"/></span><div><b>待人工审批 · {{ pendingInterrupt.toolName }}</b><p>智能体已暂停，等待你的决定后从检查点恢复继续执行。</p></div></header>
          <pre class="interrupt-payload">{{ JSON.stringify(pendingInterrupt.payload, null, 2) }}</pre>
          <div v-if="decideError" class="login-error">{{ decideError }}</div>
          <template v-if="editMode">
            <label class="form-label">修改后的参数（JSON）</label>
            <textarea class="interrupt-edit" v-model="editAction" :placeholder="JSON.stringify(pendingInterrupt.payload, null, 2)" />
            <label class="form-label">审批备注</label>
            <input class="form-input" v-model="editReason" placeholder="说明修改原因" />
          </template>
          <footer>
            <button class="button danger-ghost" :disabled="deciding" @click="decideInterrupt('reject')">{{ deciding ? '处理中…' : '驳回' }}</button>
            <button class="button secondary" :disabled="deciding" @click="editMode = !editMode">{{ editMode ? '收起编辑' : '编辑后批准' }}</button>
            <button class="button primary" :disabled="deciding" @click="decideInterrupt(editMode ? 'edit' : 'approve')">{{ deciding ? '处理中…' : (editMode ? '提交修改' : '批准') }}</button>
          </footer>
        </div>
        <div v-if="errorMessage" class="conversation-error"><CircleHelp :size="15" /><span>{{ errorMessage }}</span></div>
        <div v-if="streamContext || lastTurn" class="conversation-context-bar">
          <template v-if="streamContext">
            <span><BrainCircuit :size="13" /> 召回记忆 {{ streamContext.memoriesRecalled }} 条</span>
            <span>历史 {{ streamContext.historyMessages }} 条{{ streamContext.droppedMessages ? `（超出预算裁剪 ${streamContext.droppedMessages} 条）` : '' }}</span>
            <span>Tokens {{ streamContext.estimatedTokens }} / {{ streamContext.budgetTokens }}</span>
          </template>
          <template v-else-if="lastTurn">
            <span><BrainCircuit :size="13" /> 召回记忆 {{ lastTurn.context.memoriesRecalled }} 条</span>
            <span>历史 {{ lastTurn.context.historyMessages }} 条{{ lastTurn.context.droppedMessages ? `（超出预算裁剪 ${lastTurn.context.droppedMessages} 条）` : '' }}</span>
            <span>Tokens {{ lastTurn.context.estimatedTokens }} / {{ lastTurn.context.budgetTokens }}</span>
            <span v-if="lastTurn.memoriesUsed.length" class="memory-chips"><em v-for="memory in lastTurn.memoriesUsed.slice(0, 3)" :key="memory.id" :title="memory.content">{{ memory.key }}</em></span>
          </template>
        </div>
        <footer class="conversation-input">
          <textarea v-model="input" placeholder="输入消息，Enter 发送，Shift+Enter 换行" @keydown.enter.exact.prevent="send" />
          <button class="button primary" :disabled="sending || !input.trim()" @click="send"><Send :size="15" />{{ sending ? '回复中…' : '发送' }}</button>
        </footer>
      </template>
      <div v-else class="conversation-empty big"><Bot :size="28" /><h3>选择或新建一个对话</h3><p>每个智能体都有独立的会话、长期记忆与上下文窗口。</p></div>
    </main>

    <div v-if="showWorkspace" class="modal-layer" @click.self="showWorkspace=false">
      <section class="dialog workspace-dialog">
        <header class="dialog-head"><div><span class="dialog-kicker">AGENT WORKSPACE</span><h2>智能体工作区</h2></div><button class="icon-button" @click="showWorkspace=false"><X :size="18"/></button></header>
        <div class="dialog-body">
          <p class="dialog-text">工具模式下，智能体在项目专属工作区里读写真实文件、执行沙箱代码（AGENTS.md 为自动注入的长期记忆上下文）。</p>
          <div class="workspace-files">
            <div v-for="file in workspaceFiles" :key="file.path"><FolderOpen :size="15"/><code>{{ file.path }}</code><small>{{ fmtFileSize(file.size) }}</small></div>
            <div v-if="!workspaceLoading && !workspaceFiles.length" class="deployment-empty-row">工作区暂时没有文件 · 让工具模式智能体开始干活即可看到产物</div>
          </div>
        </div>
        <footer class="dialog-foot"><span class="dialog-note">工作区文件由智能体创建与维护</span><div><button class="button secondary" @click="showWorkspace=false">关闭</button></div></footer>
      </section>
    </div>
  </div>
</template>
