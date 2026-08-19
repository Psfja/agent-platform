<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppShell from './components/AppShell.vue'
import ToastStack from './components/ToastStack.vue'

const route=useRoute()
</script>

<template>
  <RouterView v-if="route.meta.layout === 'blank'" />
  <AppShell v-else />
  <ToastStack />
</template>
