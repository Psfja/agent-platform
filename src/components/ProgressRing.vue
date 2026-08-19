<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ value: number; size?: number; stroke?: number; color?: string }>(), { size: 64, stroke: 6, color: '#6255d9' })
const radius = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const offset = computed(() => circumference.value * (1 - props.value / 100))
</script>
<template>
  <div class="progress-ring" :style="{width:`${size}px`,height:`${size}px`}">
    <svg :width="size" :height="size"><circle class="ring-track" :cx="size/2" :cy="size/2" :r="radius" fill="none" :stroke-width="stroke"/><circle class="ring-value" :cx="size/2" :cy="size/2" :r="radius" fill="none" :stroke="color" :stroke-width="stroke" :stroke-dasharray="circumference" :stroke-dashoffset="offset"/></svg>
    <strong>{{ value }}<small>%</small></strong>
  </div>
</template>
