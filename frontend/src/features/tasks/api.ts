import { api } from '@/lib/api'
import type { Task, TaskCreate, TaskUpdate, TaskSummary, TasksListResponse, TaskFilters } from './types/tasks'

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const queryKeys = {
  tasks: {
    all: ['tasks'] as const,
    list: (filters?: TaskFilters) =>
      ['tasks', 'list', filters ?? {}] as const,
    summary: ['tasks', 'summary'] as const,
    detail: (id: string) => ['tasks', 'detail', id] as const,
  },
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export function fetchTasks(filters?: TaskFilters): Promise<TasksListResponse> {
  return api.get<TasksListResponse>('/tasks/', { params: filters as Record<string, unknown> })
}

export function fetchTaskSummary(): Promise<TaskSummary> {
  return api.get<TaskSummary>('/tasks/summary')
}

export function fetchTask(id: string): Promise<Task> {
  return api.get<Task>(`/tasks/${id}`)
}

export function createTask(body: TaskCreate): Promise<Task> {
  return api.post<Task>('/tasks/', body)
}

export function updateTask(id: string, body: TaskUpdate): Promise<Task> {
  return api.patch<Task>(`/tasks/${id}`, body)
}

export function updateTaskStatus(id: string, status: string): Promise<Task> {
  return api.patch<Task>(`/tasks/${id}/status`, { status })
}
