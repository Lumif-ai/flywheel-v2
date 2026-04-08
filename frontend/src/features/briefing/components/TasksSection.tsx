import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { isBefore, startOfDay, format } from 'date-fns'
import { Plus, Check } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'
import { useCreateTask } from '@/features/tasks/hooks/useCreateTask'
import { useUpdateTaskStatus } from '@/features/tasks/hooks/useUpdateTaskStatus'
import { VALID_TRANSITIONS } from '@/features/tasks/types/tasks'
import type { TaskStatus } from '@/features/tasks/types/tasks'
import type { TaskItem } from '@/features/briefing/types/briefing-v2'

interface TasksSectionProps {
  tasks: TaskItem[] | undefined
  isLoading: boolean
}

// ---------------------------------------------------------------------------
// Section title style (matches DailyBriefSection / TodaySection h2 pattern)
// ---------------------------------------------------------------------------

const sectionTitleStyle: React.CSSProperties = {
  fontSize: typography.sectionTitle.size,
  fontWeight: typography.sectionTitle.weight,
  lineHeight: typography.sectionTitle.lineHeight,
  color: colors.headingText,
  margin: 0,
  marginBottom: spacing.element,
}

// ---------------------------------------------------------------------------
// Source badge label mapping
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  manual: 'Manual',
  meeting: 'Meeting',
  email: 'Email',
}

// ---------------------------------------------------------------------------
// TasksSection — main exported component
// ---------------------------------------------------------------------------

export function TasksSection({ tasks, isLoading }: TasksSectionProps) {
  const isLoadingState = isLoading || tasks === undefined

  // Loading state
  if (isLoadingState) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Tasks</h2>
        <div className="space-y-3">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </BrandedCard>
    )
  }

  // Filter out tasks that are already done, dismissed, or deferred
  const activeTasks = tasks.filter(
    (t) => t.status !== 'done' && t.status !== 'dismissed' && t.status !== 'deferred',
  )

  // Empty state
  if (activeTasks.length === 0) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Tasks</h2>
        <InlineTaskQuickAdd />
        <p
          style={{
            fontSize: '13px',
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
            marginTop: spacing.element,
          }}
        >
          Add your first task to get started.
        </p>
      </BrandedCard>
    )
  }

  // Loaded state
  return (
    <BrandedCard hoverable={false}>
      <h2 style={sectionTitleStyle}>Tasks</h2>
      <InlineTaskQuickAdd />
      <div style={{ marginTop: spacing.element }}>
        {activeTasks.map((task, index) => (
          <TaskRow key={task.id} task={task} isLast={index === activeTasks.length - 1} />
        ))}
      </div>
      {/* Footer link */}
      <div
        style={{
          marginTop: spacing.element,
          paddingTop: spacing.element,
          borderTop: `1px solid ${colors.subtleBorder}`,
        }}
      >
        <NavLink
          to="/tasks"
          style={{
            fontSize: '13px',
            color: colors.brandCoral,
            fontWeight: 500,
            textDecoration: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.textDecoration = 'underline'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.textDecoration = 'none'
          }}
        >
          View all tasks &rarr;
        </NavLink>
      </div>
    </BrandedCard>
  )
}

// ---------------------------------------------------------------------------
// InlineTaskQuickAdd — text input with Plus icon, creates task on Enter
// ---------------------------------------------------------------------------

function InlineTaskQuickAdd() {
  const [title, setTitle] = useState('')
  const queryClient = useQueryClient()
  const createTask = useCreateTask()

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return
    const trimmed = title.trim()
    if (!trimmed || createTask.isPending) return

    createTask.mutate(
      {
        title: trimmed,
        task_type: 'other',
        commitment_direction: 'yours',
        priority: 'medium',
        trust_level: 'review',
        due_date: new Date().toISOString().split('T')[0],
      },
      {
        onSuccess: () => {
          setTitle('')
          queryClient.invalidateQueries({ queryKey: ['briefing-v2'] })
        },
      },
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <Plus
        size={16}
        style={{
          position: 'absolute',
          left: '12px',
          top: '50%',
          transform: 'translateY(-50%)',
          color: colors.secondaryText,
          pointerEvents: 'none',
        }}
      />
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Add a task..."
        style={{
          width: '100%',
          fontSize: '14px',
          padding: '8px 12px 8px 36px',
          border: `1px solid ${colors.subtleBorder}`,
          borderRadius: '8px',
          color: colors.bodyText,
          backgroundColor: 'transparent',
          outline: 'none',
          boxSizing: 'border-box',
        }}
        onFocus={(e) => {
          e.currentTarget.style.outline = `2px solid #E94D35`
          e.currentTarget.style.outlineOffset = '-1px'
        }}
        onBlur={(e) => {
          e.currentTarget.style.outline = 'none'
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// TaskRow — single task with checkbox, title, due date, source badge
// ---------------------------------------------------------------------------

function TaskRow({ task, isLast }: { task: TaskItem; isLast: boolean }) {
  const [checked, setChecked] = useState(false)
  const queryClient = useQueryClient()
  const updateStatus = useUpdateTaskStatus()

  const completeTask = (taskId: string, currentStatus: TaskStatus) => {
    const invalidateOpts = {
      onError: () => setChecked(false),
      onSettled: () => queryClient.invalidateQueries({ queryKey: ['briefing-v2'] }),
    }

    if (currentStatus === 'confirmed' || currentStatus === 'in_progress') {
      // Direct transition to done
      updateStatus.mutate({ id: taskId, status: 'done' }, invalidateOpts)
    } else if (currentStatus === 'detected' || currentStatus === 'in_review') {
      // Two-step: confirmed -> done
      updateStatus.mutate(
        { id: taskId, status: 'confirmed' },
        {
          onSuccess: () => {
            updateStatus.mutate({ id: taskId, status: 'done' }, invalidateOpts)
          },
          onError: () => setChecked(false),
        },
      )
    } else if (currentStatus === 'blocked') {
      // Two-step: in_progress -> done
      updateStatus.mutate(
        { id: taskId, status: 'in_progress' },
        {
          onSuccess: () => {
            updateStatus.mutate({ id: taskId, status: 'done' }, invalidateOpts)
          },
          onError: () => setChecked(false),
        },
      )
    }
    // done, dismissed, deferred: no-op (filtered out of list)
  }

  const handleCheck = () => {
    if (checked) return
    setChecked(true)
    completeTask(task.id, task.status as TaskStatus)
  }

  // Due date display
  const dueDateDisplay = formatDueDate(task.due_date)

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        paddingTop: '10px',
        paddingBottom: '10px',
        borderBottom: isLast ? 'none' : `1px solid ${colors.subtleBorder}`,
      }}
    >
      {/* Custom checkbox */}
      <button
        type="button"
        onClick={handleCheck}
        aria-label={checked ? 'Task completed' : 'Mark task complete'}
        style={{
          width: '20px',
          height: '20px',
          minWidth: '20px',
          borderRadius: '6px',
          border: checked ? '1.5px solid #E94D35' : `1.5px solid ${colors.subtleBorder}`,
          backgroundColor: checked ? '#E94D35' : 'transparent',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 0,
          transition: 'all 150ms ease',
        }}
      >
        {checked && <Check size={14} color="#fff" />}
      </button>

      {/* Title */}
      <span
        style={{
          flex: '1 1 0%',
          fontSize: '14px',
          color: checked ? colors.secondaryText : colors.headingText,
          textDecoration: checked ? 'line-through' : 'none',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {task.title}
      </span>

      {/* Due date */}
      {dueDateDisplay && (
        <span
          style={{
            fontSize: '12px',
            color: dueDateDisplay.isOverdue ? colors.error : colors.secondaryText,
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {dueDateDisplay.label}
        </span>
      )}

      {/* Source badge */}
      <Badge
        variant="secondary"
        className="text-[11px]"
        style={{ flexShrink: 0 }}
      >
        {SOURCE_LABELS[task.source] || task.source}
      </Badge>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Date formatting helper
// ---------------------------------------------------------------------------

function formatDueDate(
  dueDateStr: string | null,
): { label: string; isOverdue: boolean } | null {
  if (!dueDateStr) return null

  const dueDate = startOfDay(new Date(dueDateStr))
  const today = startOfDay(new Date())

  if (isBefore(dueDate, today)) {
    return { label: format(dueDate, 'MMM d'), isOverdue: true }
  }

  if (dueDate.getTime() === today.getTime()) {
    return { label: 'Today', isOverdue: false }
  }

  return { label: format(dueDate, 'MMM d'), isOverdue: false }
}
