export type ProjectStatus = 'planning' | 'executing' | 'completed' | 'testing' | 'deploying' | 'paused' | 'archived' | 'draft' | 'failed'
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'paused' | 'cancelled'

export interface Project {
  id: string
  name: string
  description: string
  status: ProjectStatus
  progress: number
  version: string
  template: string
  owner: string
  updatedAt: string
  members: string[]
  tasks: { done: number; total: number }
  risk: 'low' | 'medium' | 'high'
}

export interface Task {
  id: string
  parentId: string | null
  name: string
  agent: string
  agentShort: string
  status: TaskStatus
  progress: number
  duration: string
  startedAt: string
  incremental?: boolean
  description: string
  files?: number
  tokens?: string
  currentAction?: string
  iterationId?: string | null
}

export interface Iteration {
  id: string
  version: string
  title: string
  description: string
  date: string
  author: string
  status: 'analyzing' | 'executing' | 'testing' | 'deploying' | 'completed' | 'failed' | 'rolled_back'
  files: number
  added: number
  removed: number
  tests: number
  deployStatus: string
  type: 'feature' | 'fix' | 'initial'
}
