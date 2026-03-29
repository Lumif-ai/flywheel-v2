import { useState, useCallback } from 'react'
import { CheckCircle, Clock, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { Task } from '../types/tasks'
import { TaskSkillChip } from './TaskSkillChip'

type ExitAnimation = 'task-exit-confirm' | 'task-exit-dismiss' | 'task-exit-later' | null

interface TaskTriageCardProps {
  task: Task
  onConfirm: (task: Task) => void
  onLater: (task: Task) => void
  onDismiss: (task: Task) => void
  style?: React.CSSProperties
}

export function TaskTriageCard({ task, onConfirm, onLater, onDismiss, style }: TaskTriageCardProps) {
  const [exitAnim, setExitAnim] = useState<ExitAnimation>(null)

  const triggerAction = useCallback(
    (animClass: ExitAnimation, handler: (task: Task) => void) => {
      setExitAnim(animClass)
      setTimeout(() => handler(task), 150)
    },
    [task],
  )

  const provenanceText = task.meeting_id
    ? `From meeting \u00b7 ${formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}`
    : 'Manual task'

  return (
    <div
      role="listitem"
      data-task-id={task.id}
      className={`group flex items-center justify-between ${exitAnim ?? ''}`}
      style={{
        padding: '16px 20px',
        background: 'var(--card-bg)',
        border: '1px solid var(--subtle-border)',
        borderRadius: '12px',
        transition: 'background 200ms, border-color 200ms',
        ...style,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--brand-tint)'
        e.currentTarget.style.borderColor = 'rgba(233,77,53,0.15)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--card-bg)'
        e.currentTarget.style.borderColor = 'var(--subtle-border)'
      }}
      onFocus={(e) => {
        e.currentTarget.style.background = 'var(--brand-tint)'
        e.currentTarget.style.borderColor = 'rgba(233,77,53,0.15)'
      }}
      onBlur={(e) => {
        e.currentTarget.style.background = 'var(--card-bg)'
        e.currentTarget.style.borderColor = 'var(--subtle-border)'
      }}
      tabIndex={0}
    >
      {/* Left section */}
      <div className="flex flex-col gap-1 min-w-0 flex-1 mr-4">
        <span
          className="truncate"
          style={{
            fontSize: '15px',
            fontWeight: 500,
            color: 'var(--heading-text)',
          }}
        >
          {task.title}
        </span>
        <span
          style={{
            fontSize: '13px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
          }}
        >
          {provenanceText}
        </span>
        {task.suggested_skill && <TaskSkillChip skillName={task.suggested_skill} />}
      </div>

      {/* Right section — action buttons */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => triggerAction('task-exit-confirm', onConfirm)}
          aria-label="Confirm task"
          className="flex items-center justify-center rounded-md transition-colors"
          style={{
            width: '36px',
            height: '36px',
            color: 'var(--secondary-text)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--success)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--secondary-text)' }}
        >
          <CheckCircle className="size-[28px]" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => triggerAction('task-exit-later', onLater)}
          aria-label="Save for later"
          className="flex items-center justify-center rounded-md transition-colors"
          style={{
            width: '36px',
            height: '36px',
            color: 'var(--secondary-text)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--warning)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--secondary-text)' }}
        >
          <Clock className="size-[28px]" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => triggerAction('task-exit-dismiss', onDismiss)}
          aria-label="Dismiss task"
          className="flex items-center justify-center rounded-md transition-colors"
          style={{
            width: '36px',
            height: '36px',
            color: 'var(--secondary-text)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--error)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--secondary-text)' }}
        >
          <X className="size-[28px]" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  )
}
