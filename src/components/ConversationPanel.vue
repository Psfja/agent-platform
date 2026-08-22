<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { Bot, BrainCircuit, CircleHelp, LoaderCircle, MessageSquarePlus, Send, Sparkles, Trash2, UserRound, Wand2 } from 'lucide-vue-next'
import { api, ApiError, type AgentTypeRecord, type ChatTurnRecord, type ConversationMessageRecord, type ConversationRecord } from '../api/client'
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
    const detail = await api.conversation(props.projectId, id)
    messages.value = detail.messages
    lastTurn.value = null
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
      onMeta: (context) => { streamContext.value = context; scrollBottom() },
      onDelta: (chunk) => { streamingContent.value += chunk; scrollBottom() },
      onTitle: (title) => { updateConversationInList({ ...(conversations.value.find(c => c.id === currentId.value) as ConversationRecord), title }) },
    })
    if (done.title) updateConversationInList({ ...(conversations.value.find(c => c.id === currentId.value) as ConversationRecord), title: done.title })
    updateConversationInList(done.conversation)
    lastTurn.value = {
      conversation: done.conversation,
      userMessage: localUser,
      assistantMessage: done.assistantMessage,
      memoriesUsed: done.memoriesUsed,
      context: streamContext.value || { historyMessages: 0, droppedMessages: 0, estimatedTokens: 0, budgetTokens: 0, memoriesRecalled: 0, skillsLoaded: 0 },
    }
    streamContext.value = null
    finishWith(done.assistantMessage)
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
        finishWith(turn.assistantMessage)
      } catch (fallbackError) { showError(fallbackError) }
    }
  } finally { sending.value = false; await scrollBottom() }
}
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
          <label class="remember-toggle" title="开启后每轮对话自动提取值得记住的事实写入长期记忆"><input type="checkbox" v-model="remember" /><i></i><span><BrainCircuit :size="13"/>对话提取记忆</span></label>
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
  </div>
</template>
