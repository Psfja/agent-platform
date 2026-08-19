<script setup lang="ts">
import { CheckCircle2, X } from 'lucide-vue-next'
import { useAppStore } from '../stores/app'
const app = useAppStore()
</script>

<template>
  <TransitionGroup name="toast" tag="div" class="toast-stack">
    <div class="toast" v-for="item in app.toasts" :key="item.id">
      <CheckCircle2 :size="18" />
      <div><strong>{{ item.title }}</strong><span>{{ item.message }}</span></div>
      <button class="icon-button" @click="app.dismissToast(item.id)"><X :size="15" /></button>
    </div>
  </TransitionGroup>
</template>
