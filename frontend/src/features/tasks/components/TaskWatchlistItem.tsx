import { isBefore, startOfDay, differenceInDays, formatDistanceToNow } from 'date-fns'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Task } from '../types/tasks'

interface TaskWatchlistItemProps {
  task: Task
  onCreateFollowUp: (task: Task) => void
  hasFollowUp?: boolean
}

function getInitials(task: Task): string {
  // Use first two letters of the title as a simple fallback
  const words = task.title.split(' ')
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return task.title.slice(0, 2).toUpperCase()
}

export function TaskWatchlistItem({ task, onCreateFollowUp, hasFollowUp = false }: TaskWatchlistItemProps) {
  const isOverdue = task.due_date && isBefore(startOfDay(new Date(task.due_date)), startOfDay(new Date()))
  const daysOverdue = isOverdue
    ? differenceInDays(startOfDay(new Date()), startOfDay(new Date(task.due_date!)))
    : 0

  return (
    <div
      data-task-id={task.id}
      className="transition-colors duration-150"
      style={{
        padding: '16px 20px',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--brand-tint)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      {/* Row 1: Avatar + person/meeting name + company */}
      <div className="flex items-center gap-2.5" style={{ marginBottom: '4px' }}>
        {/* Avatar */}
        <div
          className="shrink-0 flex items-center justify-center rounded-full"
          style={{
            width: '24px',
            height: '24px',
            background: 'var(--brand-tint)',
            color: 'var(--brand-coral)',
            fontSize: '10px',
            fontWeight: 600,
          }}
        >
          {getInitials(task)}
        </div>
        <span
          style={{
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--heading-text)',
          }}
        >
          {task.meeting_id ? 'Meeting contact' : 'Manual task'}
        </span>
        {task.account_id && task.metadata?.account_name != null && (
          <>
            <span style={{ color: 'var(--secondary-text)', fontSize: '14px' }}>&middot;</span>
            <span
              style={{
                fontSize: '14px',
                fontWeight: 400,
                color: 'var(--secondary-text)',
              }}
            >
              {String(task.metadata!.account_name)}
            </span>
          </>
        )}
      </div>

      {/* Row 2: Promise text (task title) */}
      <p
        style={{
          fontSize: '14px',
          fontWeight: 400,
          color: 'var(--heading-text)',
          fontStyle: 'italic',
          margin: '0 0 4px 0',
        }}
      >
        &ldquo;{task.title}&rdquo;
      </p>

      {/* Row 3: Provenance + Status indicator */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        {/* Left: Provenance */}
        <span
          style={{
            fontSize: '13px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
          }}
        >
          From: {task.meeting_id
            ? `Meeting \u00b7 ${formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}`
            : 'Manual'}
        </span>

        {/* Right: Status indicator */}
        <div className="flex items-center gap-2">
          {isOverdue ? (
            <>
              {/* Red dot */}
              <span
                className="shrink-0 rounded-full"
                style={{
                  width: '8px',
                  height: '8px',
                  background: 'var(--task-overdue-dot)',
                  display: 'inline-block',
                }}
              />
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 500,
                  color: 'var(--task-overdue-text)',
                }}
              >
                Overdue ({daysOverdue} day{daysOverdue !== 1 ? 's' : ''})
              </span>
              {hasFollowUp ? (
                <Badge variant="secondary">Follow-up created</Badge>
              ) : (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={(e) => {
                    e.stopPropagation()
                    onCreateFollowUp(task)
                  }}
                  style={{ color: 'var(--task-overdue-text)' }}
                >
                  Create Follow-up
                </Button>
              )}
            </>
          ) : (
            <>
              {/* Green dot */}
              <span
                className="shrink-0 rounded-full"
                style={{
                  width: '8px',
                  height: '8px',
                  background: 'var(--task-ontrack-dot)',
                  display: 'inline-block',
                }}
              />
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 400,
                  color: 'var(--secondary-text)',
                }}
              >
                On track
                {task.due_date && (
                  <> &middot; {new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</>
                )}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
