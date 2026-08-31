<script setup lang="ts">
import { computed, ref } from 'vue'
import { GitBranch, MousePointerClick, Workflow } from 'lucide-vue-next'
import { layoutNodes, wouldCreateCycle, type FlowNodeLike } from './flowLayout'

export interface FlowNode extends FlowNodeLike {
  agentTypeId: string
  displayName: string
  executionMode: 'sequential' | 'parallel'
}

const props = defineProps<{
  modelValue: FlowNode[]
  agents: { id: string; name: string }[]
}>()
const emit = defineEmits<{
  'update:modelValue': [value: FlowNode[]]
  select: [nodeKey: string | null]
}>()

const VIEW_W = 960
const VIEW_H = 480
const NODE_W = 150
const NODE_H = 64

const svgRef = ref<SVGSVGElement | null>(null)
const selectedNodeKey = ref<string | null>(null)
const selectedEdge = ref<string | null>(null) // `${from}>${to}`

type DragState = { kind: 'node'; nodeKey: string; offsetX: number; offsetY: number } | { kind: 'edge'; from: string; x: number; y: number }
const drag = ref<DragState | null>(null)

function agentName(id: string): string {
  return props.agents.find(a => a.id === id)?.name || id
}
function agentInitials(id: string): string {
  return agentName(id).slice(0, 2)
}
function nodePos(node: FlowNode): { x: number; y: number } {
  const canvas = node.config?.canvas
  return canvas && typeof canvas.x === 'number' && typeof canvas.y === 'number' ? { x: canvas.x, y: canvas.y } : { x: 120, y: 120 }
}
function setNodePos(node: FlowNode, x: number, y: number) {
  node.config = { ...(node.config || {}), canvas: { x: Math.round(x), y: Math.round(y) } }
}
function findNode(key: string): FlowNode | undefined {
  return props.modelValue.find(n => n.nodeKey === key)
}
function emitChange() {
  emit('update:modelValue', props.modelValue)
}
function select(key: string | null) {
  selectedNodeKey.value = key
  emit('select', key)
}

function toSvg(e: PointerEvent): { x: number; y: number } {
  const svg = svgRef.value
  if (!svg) return { x: 0, y: 0 }
  const rect = svg.getBoundingClientRect()
  return {
    x: ((e.clientX - rect.left) / rect.width) * VIEW_W,
    y: ((e.clientY - rect.top) / rect.height) * VIEW_H,
  }
}

// ---- 节点拖拽 ----
function onNodeDown(e: PointerEvent, node: FlowNode) {
  const target = e.target as Element
  if (target.closest('[data-handle]') || target.closest('[data-node-btn]')) return
  select(node.nodeKey)
  const pos = nodePos(node)
  const point = toSvg(e)
  drag.value = { kind: 'node', nodeKey: node.nodeKey, offsetX: point.x - pos.x, offsetY: point.y - pos.y }
  svgRef.value?.setPointerCapture(e.pointerId)
}

// ---- 连线拖拽（从输出把手拖到目标输入把手） ----
function onOutputDown(e: PointerEvent, node: FlowNode) {
  e.stopPropagation()
  select(node.nodeKey)
  const point = toSvg(e)
  drag.value = { kind: 'edge', from: node.nodeKey, x: point.x, y: point.y }
  svgRef.value?.setPointerCapture(e.pointerId)
}

function onMove(e: PointerEvent) {
  if (!drag.value) return
  const point = toSvg(e)
  if (drag.value.kind === 'node') {
    const node = findNode(drag.value.nodeKey)
    if (node) setNodePos(node, point.x - drag.value.offsetX, point.y - drag.value.offsetY)
  } else {
    drag.value.x = point.x
    drag.value.y = point.y
  }
}

function inputHandlePoint(node: FlowNode): { x: number; y: number } {
  const pos = nodePos(node)
  return { x: pos.x, y: pos.y + NODE_H / 2 }
}

function onUp(e: PointerEvent) {
  const current = drag.value
  drag.value = null
  try { svgRef.value?.releasePointerCapture(e.pointerId) } catch { /* noop */ }
  if (!current) return
  if (current.kind === 'node') {
    emitChange()
    return
  }
  // 命中检测：目标节点的输入把手
  const point = { x: current.x, y: current.y }
  const target = props.modelValue.find(node => {
    const p = inputHandlePoint(node)
    return Math.hypot(p.x - point.x, p.y - point.y) < 18
  })
  if (target && target.nodeKey !== current.from) {
    if (!target.dependsOn.includes(current.from) && !wouldCreateCycle(props.modelValue, current.from, target.nodeKey)) {
      target.dependsOn = [...target.dependsOn, current.from]
      selectedEdge.value = `${current.from}>${target.nodeKey}`
      emitChange()
    }
  }
}

// ---- 边渲染 ----
interface Edge { from: string; to: string }
const edges = computed<Edge[]>(() => {
  const result: Edge[] = []
  for (const node of props.modelValue) {
    for (const dep of node.dependsOn) {
      if (findNode(dep)) result.push({ from: dep, to: node.nodeKey })
    }
  }
  return result
})

function edgePath(edge: Edge): string {
  const from = findNode(edge.from)
  const to = findNode(edge.to)
  if (!from || !to) return ''
  const fp = nodePos(from)
  const tp = nodePos(to)
  const x1 = fp.x + NODE_W
  const y1 = fp.y + NODE_H / 2
  const x2 = tp.x
  const y2 = tp.y + NODE_H / 2
  const dx = Math.max(36, (x2 - x1) / 2)
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
}
function edgeMid(edge: Edge): { x: number; y: number } {
  const from = findNode(edge.from)
  const to = findNode(edge.to)
  if (!from || !to) return { x: 0, y: 0 }
  const fp = nodePos(from)
  const tp = nodePos(to)
  return { x: (fp.x + NODE_W + tp.x) / 2, y: (fp.y + tp.y + NODE_H) / 2 }
}
function edgeMode(edge: Edge): string {
  const target = findNode(edge.to)
  return target?.executionMode || 'sequential'
}
function removeEdge(edge: Edge) {
  const target = findNode(edge.to)
  if (!target) return
  target.dependsOn = target.dependsOn.filter(d => d !== edge.from)
  selectedEdge.value = null
  emitChange()
}

function removeNode(node: FlowNode) {
  const index = props.modelValue.indexOf(node)
  if (index < 0) return
  props.modelValue.splice(index, 1)
  for (const other of props.modelValue) {
    if (other.dependsOn.includes(node.nodeKey)) other.dependsOn = other.dependsOn.filter(d => d !== node.nodeKey)
  }
  if (selectedNodeKey.value === node.nodeKey) select(null)
  selectedEdge.value = null
  emitChange()
}

defineExpose({
  autoLayout() {
    layoutNodes(props.modelValue)
    emitChange()
  },
})
</script>

<template>
  <div class="flow-canvas-wrap" :class="{ empty: !modelValue.length }">
    <svg
      ref="svgRef"
      class="flow-canvas"
      :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
      preserveAspectRatio="xMidYMid meet"
      @pointermove="onMove"
      @pointerup="onUp"
      @pointercancel="onUp"
    >
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#8a94a7" />
        </marker>
        <marker id="flow-arrow-parallel" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#d68a21" />
        </marker>
      </defs>

      <!-- 依赖连线 -->
      <g v-for="edge in edges" :key="`${edge.from}>${edge.to}`" class="flow-edge-group">
        <path
          class="flow-edge-hit"
          :d="edgePath(edge)"
          fill="none"
          stroke="transparent"
          stroke-width="14"
          @pointerdown.stop="selectedEdge = `${edge.from}>${edge.to}`"
        />
        <path
          class="flow-edge"
          :class="{ parallel: edgeMode(edge) === 'parallel', selected: selectedEdge === `${edge.from}>${edge.to}` }"
          :d="edgePath(edge)"
          fill="none"
          :stroke-width="edgeMode(edge) === 'parallel' ? 2 : 1.8"
          :marker-end="edgeMode(edge) === 'parallel' ? 'url(#flow-arrow-parallel)' : 'url(#flow-arrow)'"
        />
        <g v-if="selectedEdge === `${edge.from}>${edge.to}`" class="flow-edge-remove" :transform="`translate(${edgeMid(edge).x}, ${edgeMid(edge).y})`" @pointerdown.stop @click="removeEdge(edge)">
          <circle r="9" /><path d="M -4 -4 L 4 4 M 4 -4 L -4 4" stroke="#fff" stroke-width="2" />
        </g>
      </g>

      <!-- 连线拖拽预览 -->
      <path v-if="drag && drag.kind === 'edge'" class="flow-temp-line" :d="`M ${nodePos(findNode(drag.from)!).x + NODE_W} ${nodePos(findNode(drag.from)!).y + NODE_H / 2} C ${nodePos(findNode(drag.from)!).x + NODE_W + 60} ${nodePos(findNode(drag.from)!).y + NODE_H / 2}, ${drag.x - 60} ${drag.y}, ${drag.x} ${drag.y}`" fill="none" stroke="#6255d9" stroke-width="2" stroke-dasharray="6 5" />

      <!-- 节点 -->
      <g
        v-for="node in modelValue"
        :key="node.nodeKey"
        class="flow-node-group"
        :class="{ selected: selectedNodeKey === node.nodeKey }"
        :transform="`translate(${nodePos(node).x}, ${nodePos(node).y})`"
        @pointerdown="onNodeDown($event, node)"
        @click="select(node.nodeKey)"
      >
        <rect class="flow-node-bg" :class="{ parallel: node.executionMode === 'parallel' }" width="150" height="64" rx="11" />
        <circle data-handle class="flow-handle" cx="0" cy="32" r="6.5" />
        <circle data-handle class="flow-handle out" cx="150" cy="32" r="6.5" @pointerdown="onOutputDown($event, node)" />
        <rect class="flow-node-icon" x="12" y="14" width="36" height="36" rx="8" />
        <text class="flow-node-initials" x="30" y="36" text-anchor="middle">{{ agentInitials(node.agentTypeId) }}</text>
        <text class="flow-node-name" x="58" y="30">{{ node.displayName }}</text>
        <text class="flow-node-mode" x="58" y="48" :class="{ parallel: node.executionMode === 'parallel' }">{{ node.executionMode === 'parallel' ? '⇉ 并行' : '→ 顺序' }}</text>
        <g data-node-btn class="flow-node-remove" transform="translate(150, 0)" @pointerdown.stop @click.stop="removeNode(node)">
          <circle r="8.5" /><path d="M -3.5 -3.5 L 3.5 3.5 M 3.5 -3.5 L -3.5 3.5" stroke="#fff" stroke-width="1.8" />
        </g>
      </g>
    </svg>
    <div v-if="!modelValue.length" class="flow-empty-hint">
      <Workflow :size="26" />
      <b>画布为空</b>
      <p>通过「AI 生成流程」或点击上方「添加节点」开始编排。<br/>拖拽节点调整位置；从节点右侧圆点拖到另一节点左侧圆点建立依赖。</p>
    </div>
    <div class="flow-legend">
      <span><i class="edge-sequential"></i>顺序依赖</span>
      <span><i class="edge-parallel"></i>并行汇聚</span>
      <span><GitBranch :size="12" /> 右侧圆点拖出连线</span>
      <span><MousePointerClick :size="12" /> 点击连线可删除</span>
    </div>
  </div>
</template>
