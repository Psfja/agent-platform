<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string; label?: string }>()
const labelMap: Record<string, string> = {
  planning: '规划中', executing: '执行中', in_progress: '执行中', completed: '已完成', testing: '测试中', deploying: '部署中',
  pending: '待执行', failed: '失败', cancelled: '已终止', paused: '已暂停', archived: '已归档', draft: '草稿', running: '运行中',
  low: '低风险', medium: '中风险', high: '高风险', passed: '已通过',
}
const text = computed(() => props.label || labelMap[props.status] || props.status)
</script>

<template>
  <span class="status-badge" :class="`status-${status}`"><i></i>{{ text }}</span>
</template>
