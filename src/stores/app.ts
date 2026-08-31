import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiError, authTokens, type AuthUser } from '../api/client'
import type { Project } from '../types'

export const useAppStore = defineStore('app', () => {
  const projects = ref<Project[]>([])
  const projectsLoading = ref(false)
  const backendConnected = ref(false)
  const currentUser = ref<AuthUser | null>(null)
  const sidebarCollapsed = ref(false)
  const notificationsOpen = ref(false)
  const toasts = ref<{ id: number; title: string; message: string }[]>([])
  let toastId = 0

  async function initAuth() {
    if (!authTokens.access()) { currentUser.value = null; return false }
    try { currentUser.value = await api.me(); return true } catch { currentUser.value = null; return false }
  }
  async function logout() { await api.logout(); currentUser.value = null; window.location.assign('/login') }

  async function loadProjects(silent = true) {
    projectsLoading.value = true
    try {
      projects.value = await api.projects()
      backendConnected.value = true
    } catch (error) {
      backendConnected.value = false
      projects.value = []
      if (!silent) toast('后端暂不可用', error instanceof Error ? error.message : '无法加载项目列表。')
    } finally {
      projectsLoading.value = false
    }
  }
  async function createProject(payload: { name: string; description: string; template: string; autoBuild?: boolean }) {
    try {
      const project = await api.createProject(payload)
      projects.value.unshift(project)
      backendConnected.value = true
      return project
    } catch (error) {
      const message = error instanceof ApiError ? error.message : '无法连接后端服务'
      toast('创建失败', message)
      throw error
    }
  }
  function addProject(project: Project) { projects.value.unshift(project) }
  function replaceProject(project: Project) {
    const index = projects.value.findIndex(item => item.id === project.id)
    if (index >= 0) projects.value[index] = project
    else projects.value.unshift(project)
  }
  function toast(title: string, message: string) {
    const id = ++toastId
    toasts.value.push({ id, title, message })
    window.setTimeout(() => dismissToast(id), 3500)
  }
  function dismissToast(id: number) { toasts.value = toasts.value.filter(item => item.id !== id) }

  return { projects, projectsLoading, backendConnected, currentUser, sidebarCollapsed, notificationsOpen, toasts, initAuth, logout, loadProjects, createProject, addProject, replaceProject, toast, dismissToast }
})
