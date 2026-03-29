import { startOfDay, startOfWeek, endOfWeek, addWeeks, isBefore, isEqual } from 'date-fns'

// ---------------------------------------------------------------------------
// Enum-like constants (mirrors backend VALID_* sets)
// ---------------------------------------------------------------------------

export const TASK_STATUSES = [
  'detected',
  'in_review',
  'confirmed',
  'in_progress',
  'done',
  'blocked',
  'dismissed',
  'deferred',
] as const

export const COMMITMENT_DIRECTIONS = [
  'yours',
  'theirs',
  'mutual',
  'signal',
  'speculation',
] as const

export const PRIORITIES = ['high', 'medium', 'low'] as const

export const TASK_TYPES = [
  'followup',
  'deliverable',
  'introduction',
  'research',
  'other',
] as const

export const TRUST_LEVELS = ['auto', 'review', 'confirm'] as const

// ---------------------------------------------------------------------------
// Type aliases
// ---------------------------------------------------------------------------

export type TaskStatus = (typeof TASK_STATUSES)[number]
export type CommitmentDirection = (typeof COMMITMENT_DIRECTIONS)[number]
export type Priority = (typeof PRIORITIES)[number]
export type TaskType = (typeof TASK_TYPES)[number]
export type TrustLevel = (typeof TRUST_LEVELS)[number]

// ---------------------------------------------------------------------------
// Interfaces (mirrors backend Pydantic schemas)
// ---------------------------------------------------------------------------

export interface Task {
  id: string
  tenant_id: string
  user_id: string
  meeting_id: string | null
  account_id: string | null
  title: string
  description: string | null
  source: string
  task_type: TaskType
  commitment_direction: CommitmentDirection
  suggested_skill: string | null
  skill_context: Record<string, unknown> | null
  trust_level: TrustLevel
  status: TaskStatus
  priority: Priority
  due_date: string | null
  completed_at: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  title: string
  description?: string | null
  task_type: TaskType
  commitment_direction?: CommitmentDirection
  suggested_skill?: string | null
  skill_context?: Record<string, unknown> | null
  trust_level?: TrustLevel
  priority?: Priority
  due_date?: string | null
  meeting_id?: string | null
  account_id?: string | null
}

export interface TaskUpdate {
  title?: string | null
  description?: string | null
  priority?: Priority | null
  due_date?: string | null
  suggested_skill?: string | null
  trust_level?: TrustLevel | null
}

export interface TaskSummary {
  detected: number
  in_review: number
  confirmed: number
  in_progress: number
  done: number
  blocked: number
  dismissed: number
  deferred: number
  overdue: number
}

export interface TasksListResponse {
  tasks: Task[]
  total: number
}

export interface TaskFilters {
  status?: TaskStatus
  commitment_direction?: CommitmentDirection
  priority?: Priority
  meeting_id?: string
  account_id?: string
  offset?: number
  limit?: number
}

// ---------------------------------------------------------------------------
// State machine transitions (mirrors backend VALID_TRANSITIONS)
// ---------------------------------------------------------------------------

export const VALID_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  detected: ['in_review', 'confirmed', 'dismissed', 'deferred'],
  in_review: ['confirmed', 'dismissed', 'deferred'],
  confirmed: ['in_review', 'in_progress', 'done', 'dismissed'],
  in_progress: ['done', 'blocked', 'dismissed'],
  blocked: ['in_progress', 'dismissed'],
  done: [],
  dismissed: ['detected'],
  deferred: ['in_review'],
}

// ---------------------------------------------------------------------------
// Date grouping utility
// ---------------------------------------------------------------------------

export interface GroupedTasks {
  overdue: Task[]
  today: Task[]
  thisWeek: Task[]
  nextWeek: Task[]
  later: Task[]
}

export function groupTasksByDueDate(tasks: Task[]): GroupedTasks {
  const now = new Date()
  const todayStart = startOfDay(now)
  const tomorrowStart = new Date(todayStart)
  tomorrowStart.setDate(tomorrowStart.getDate() + 1)
  const weekEnd = endOfWeek(now, { weekStartsOn: 1 })
  const nextWeekEnd = endOfWeek(addWeeks(now, 1), { weekStartsOn: 1 })

  const groups: GroupedTasks = {
    overdue: [],
    today: [],
    thisWeek: [],
    nextWeek: [],
    later: [],
  }

  for (const task of tasks) {
    if (!task.due_date) {
      groups.later.push(task)
      continue
    }

    const dueDate = startOfDay(new Date(task.due_date))

    if (isBefore(dueDate, todayStart)) {
      groups.overdue.push(task)
    } else if (isEqual(dueDate, todayStart)) {
      groups.today.push(task)
    } else if (isBefore(dueDate, weekEnd) || isEqual(dueDate, weekEnd)) {
      groups.thisWeek.push(task)
    } else if (isBefore(dueDate, nextWeekEnd) || isEqual(dueDate, nextWeekEnd)) {
      groups.nextWeek.push(task)
    } else {
      groups.later.push(task)
    }
  }

  return groups
}
