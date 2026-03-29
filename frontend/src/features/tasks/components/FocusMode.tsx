import { useEffect, useRef, useState, useCallback } from 'react'
import { X, CheckCircle, Clock, Calendar } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { toast } from 'sonner'
import { useFocusModeStore } from '../stores/focusModeStore'
import { useUpdateTaskStatus } from '../hooks/useUpdateTaskStatus'
import { useUpdateTask } from '../hooks/useUpdateTask'
import { TaskSkillChip } from './TaskSkillChip'
import type { Task, TaskStatus, Priority } from '../types/tasks'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FocusModeProps {
  tasks: Task[]
  isOpen: boolean
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Priority badge (inline helper)
// ---------------------------------------------------------------------------

const PRIORITY_COLORS: Record<Priority, { bg: string; text: string }> = {
  high: { bg: 'rgba(239,68,68,0.1)', text: '#dc2626' },
  medium: { bg: 'rgba(245,158,11,0.1)', text: '#d97706' },
  low: { bg: 'rgba(107,114,128,0.1)', text: '#6b7280' },
}

const DIRECTION_LABELS: Record<string, string> = {
  yours: 'Your commitment',
  theirs: 'Their commitment',
  mutual: 'Mutual commitment',
  signal: 'Signal',
  speculation: 'Speculation',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FocusMode({ tasks, isOpen, onClose }: FocusModeProps) {
  const store = useFocusModeStore()
  const statusMutation = useUpdateTaskStatus()
  const updateMutation = useUpdateTask()
  const overlayRef = useRef<HTMLDivElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  // Edit mode local state
  const [editTitle, setEditTitle] = useState('')
  const [editPriority, setEditPriority] = useState<Priority>('medium')
  const [editDueDate, setEditDueDate] = useState('')

  // Animation state for CSS classes
  const [exitClass, setExitClass] = useState<string | null>(null)
  const [enterClass, setEnterClass] = useState<string | null>(null)

  const currentTask = tasks[store.currentIndex] as Task | undefined
  const totalTasks = tasks.length
  const reviewedCount = store.currentIndex

  // Reset store when opening
  useEffect(() => {
    if (isOpen) {
      store.reset()
      setExitClass(null)
      setEnterClass(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // Sync edit fields when current task changes
  useEffect(() => {
    if (currentTask) {
      setEditTitle(currentTask.title)
      setEditPriority(currentTask.priority)
      setEditDueDate(currentTask.due_date ?? '')
    }
  }, [currentTask])

  // Auto-close after completion
  useEffect(() => {
    if (!store.isComplete) return
    const timer = setTimeout(() => {
      store.reset()
      onClose()
    }, 2000)
    return () => clearTimeout(timer)
  }, [store.isComplete, onClose, store])

  // Focus trap: auto-focus overlay on open
  useEffect(() => {
    if (isOpen && overlayRef.current) {
      overlayRef.current.focus()
    }
  }, [isOpen, store.currentIndex])

  // ---------------------------------------------------------------------------
  // Action handler
  // ---------------------------------------------------------------------------

  const handleAction = useCallback(
    (newStatus: TaskStatus, direction: 'left' | 'right' | 'down', label: string) => {
      if (!currentTask || exitClass) return

      // 1. Set exit animation
      const exitCls =
        direction === 'right'
          ? 'focus-card-exit-right'
          : direction === 'left'
            ? 'focus-card-exit-left'
            : 'focus-card-exit-down'
      setExitClass(exitCls)

      // 2. Call mutation
      const prevStatus = currentTask.status
      statusMutation.mutate(
        { id: currentTask.id, status: newStatus },
        {
          onSuccess: () => {
            toast(label, {
              action: {
                label: 'Undo',
                onClick: () => statusMutation.mutate({ id: currentTask.id, status: prevStatus }),
              },
              duration: 5000,
            })
          },
        },
      )

      // 3. After exit animation (250ms), advance
      setTimeout(() => {
        setExitClass(null)

        if (store.currentIndex + 1 >= totalTasks) {
          store.setComplete()
        } else {
          store.nextTask(null)
          // Trigger enter animation
          setEnterClass('focus-card-enter')
          setTimeout(() => setEnterClass(null), 400)
        }
      }, 250)
    },
    [currentTask, exitClass, statusMutation, store, totalTasks],
  )

  const handleConfirm = useCallback(
    () => handleAction('confirmed', 'right', 'Task confirmed'),
    [handleAction],
  )

  const handleDismiss = useCallback(
    () => handleAction('dismissed', 'left', 'Task dismissed'),
    [handleAction],
  )

  const handleLater = useCallback(
    () => handleAction('deferred', 'down', 'Task saved for later'),
    [handleAction],
  )

  // ---------------------------------------------------------------------------
  // Edit mode handlers
  // ---------------------------------------------------------------------------

  const handleEditSave = useCallback(() => {
    if (!currentTask) return
    const updates: Record<string, unknown> = {}
    if (editTitle !== currentTask.title) updates.title = editTitle
    if (editPriority !== currentTask.priority) updates.priority = editPriority
    if (editDueDate !== (currentTask.due_date ?? '')) {
      updates.due_date = editDueDate || null
    }
    if (Object.keys(updates).length > 0) {
      updateMutation.mutate({ id: currentTask.id, body: updates })
    }
    store.setEditing(false)
  }, [currentTask, editTitle, editPriority, editDueDate, updateMutation, store])

  // ---------------------------------------------------------------------------
  // Keyboard shortcuts
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isOpen || store.isComplete) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture keys when editing
      if (store.isEditing) {
        if (e.key === 'Escape') {
          e.preventDefault()
          store.setEditing(false)
        } else if (e.key === 'Enter') {
          e.preventDefault()
          handleEditSave()
        }
        return
      }

      switch (e.key) {
        case 'ArrowRight':
        case 'Enter':
          e.preventDefault()
          handleConfirm()
          break
        case 'ArrowLeft':
        case 'Backspace':
          e.preventDefault()
          handleDismiss()
          break
        case 'ArrowDown':
        case 's':
        case 'S':
          e.preventDefault()
          handleLater()
          break
        case 'e':
        case 'E':
          e.preventDefault()
          store.setEditing(true)
          break
        case 'Escape':
          e.preventDefault()
          onClose()
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, store.isComplete, store.isEditing, store, handleConfirm, handleDismiss, handleLater, handleEditSave, onClose])

  // ---------------------------------------------------------------------------
  // Focus trap (basic Tab handling)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isOpen) return

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !overlayRef.current) return
      const focusable = overlayRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleTab)
    return () => document.removeEventListener('keydown', handleTab)
  }, [isOpen])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!isOpen) return null

  // Completion state
  if (store.isComplete) {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Task review complete"
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ background: 'rgba(0,0,0,0.5)' }}
      >
        <div className="flex flex-col items-center gap-4 text-center focus-completion-enter">
          <CheckCircle
            className="size-12"
            style={{ color: 'var(--success)' }}
          />
          <h2
            style={{
              fontSize: '18px',
              fontWeight: 600,
              lineHeight: '1.4',
              color: 'white',
            }}
          >
            All caught up
          </h2>
          <p
            style={{
              fontSize: '13px',
              fontWeight: 400,
              color: 'rgba(255,255,255,0.7)',
            }}
          >
            {totalTasks} task{totalTasks !== 1 ? 's' : ''} reviewed
          </p>
          <button
            onClick={() => {
              store.reset()
              onClose()
            }}
            className="mt-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: 'rgba(255,255,255,0.15)',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.2)',
            }}
          >
            Close
          </button>
        </div>
      </div>
    )
  }

  if (!currentTask) return null

  const progressPercent = totalTasks > 0 ? (reviewedCount / totalTasks) * 100 : 0
  const meetingName = currentTask.metadata?.meeting_name as string | undefined
  const accountName = currentTask.metadata?.account_name as string | undefined

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label="Task review"
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      tabIndex={-1}
    >
      {/* Aria-live region for screen readers */}
      <div aria-live="polite" className="sr-only">
        Reviewing task {reviewedCount + 1} of {totalTasks}
      </div>

      {/* Header */}
      <div
        className="flex items-center justify-between px-6 pt-5 pb-3"
        style={{ maxWidth: '640px', width: '100%', margin: '0 auto' }}
      >
        <span
          style={{
            fontSize: '14px',
            fontWeight: 500,
            color: 'rgba(255,255,255,0.8)',
          }}
        >
          Reviewing {reviewedCount + 1} of {totalTasks}
        </span>
        <button
          onClick={onClose}
          aria-label="Exit focus mode"
          className="flex items-center justify-center rounded-md transition-colors"
          style={{
            width: '32px',
            height: '32px',
            color: 'rgba(255,255,255,0.6)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'white'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'rgba(255,255,255,0.6)'
          }}
        >
          <X className="size-5" />
        </button>
      </div>

      {/* Progress bar */}
      <div
        style={{
          maxWidth: '640px',
          width: '100%',
          margin: '0 auto',
          padding: '0 24px',
        }}
      >
        <div
          style={{
            height: '4px',
            borderRadius: '2px',
            background: 'rgba(255,255,255,0.15)',
            overflow: 'hidden',
          }}
          role="progressbar"
          aria-valuenow={reviewedCount}
          aria-valuemin={0}
          aria-valuemax={totalTasks}
        >
          <div
            style={{
              height: '100%',
              width: `${progressPercent}%`,
              background: 'var(--brand-coral)',
              borderRadius: '2px',
              transition: 'width 300ms ease-out',
            }}
          />
        </div>
        <span className="sr-only">{Math.round(progressPercent)}% complete</span>
      </div>

      {/* Card area */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div
          ref={cardRef}
          className={`w-full ${exitClass ?? ''} ${enterClass ?? ''}`}
          style={{
            maxWidth: '560px',
            background: 'var(--card-bg)',
            borderRadius: '16px',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            padding: '32px',
          }}
        >
          {/* Title */}
          {store.isEditing ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              autoFocus
              className="w-full rounded-lg border px-3 py-2 outline-none"
              style={{
                fontSize: '20px',
                fontWeight: 600,
                color: 'var(--heading-text)',
                borderColor: 'var(--subtle-border)',
                background: 'var(--page-bg)',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = 'var(--brand-coral)'
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = 'var(--subtle-border)'
              }}
            />
          ) : (
            <h3
              style={{
                fontSize: '20px',
                fontWeight: 600,
                color: 'var(--heading-text)',
                lineHeight: 1.3,
                margin: 0,
              }}
            >
              {currentTask.title}
            </h3>
          )}

          {/* Divider */}
          <div
            style={{
              height: '1px',
              background: 'var(--subtle-border)',
              margin: '16px 0',
            }}
          />

          {/* Metadata rows */}
          <div className="flex flex-col gap-3">
            {/* Meeting */}
            {(meetingName || currentTask.meeting_id) && (
              <div className="flex items-start gap-2">
                <span
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--secondary-text)',
                    minWidth: '70px',
                  }}
                >
                  Meeting
                </span>
                <span style={{ fontSize: '14px', color: 'var(--body-text)' }}>
                  {meetingName ?? 'From meeting'}
                  {currentTask.created_at && (
                    <>
                      {' '}
                      <span style={{ color: 'var(--secondary-text)' }}>
                        &middot;{' '}
                        {formatDistanceToNow(new Date(currentTask.created_at), {
                          addSuffix: true,
                        })}
                      </span>
                    </>
                  )}
                </span>
              </div>
            )}

            {/* Account */}
            {accountName && (
              <div className="flex items-start gap-2">
                <span
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--secondary-text)',
                    minWidth: '70px',
                  }}
                >
                  Account
                </span>
                <span style={{ fontSize: '14px', color: 'var(--body-text)' }}>
                  {accountName}
                </span>
              </div>
            )}

            {/* Commitment direction */}
            <div className="flex items-center gap-2">
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 500,
                  color: 'var(--secondary-text)',
                  minWidth: '70px',
                }}
              >
                Type
              </span>
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5"
                style={{
                  fontSize: '12px',
                  fontWeight: 500,
                  background: 'rgba(107,114,128,0.1)',
                  color: 'var(--body-text)',
                }}
              >
                {DIRECTION_LABELS[currentTask.commitment_direction] ??
                  currentTask.commitment_direction}
              </span>
            </div>

            {/* Suggested skill */}
            {currentTask.suggested_skill && (
              <div className="flex items-center gap-2">
                <span
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--secondary-text)',
                    minWidth: '70px',
                  }}
                >
                  Skill
                </span>
                <TaskSkillChip skillName={currentTask.suggested_skill} />
              </div>
            )}

            {/* Description */}
            {currentTask.description && (
              <p
                style={{
                  fontSize: '14px',
                  fontWeight: 400,
                  color: 'var(--secondary-text)',
                  lineHeight: 1.5,
                  margin: '4px 0 0',
                }}
              >
                {currentTask.description}
              </p>
            )}

            {/* Priority + Due date row */}
            <div className="flex items-center gap-3 mt-1">
              {store.isEditing ? (
                <>
                  {/* Priority toggle */}
                  <div className="flex items-center gap-1 rounded-lg border" style={{ borderColor: 'var(--subtle-border)', padding: '2px' }}>
                    {(['high', 'medium', 'low'] as Priority[]).map((p) => (
                      <button
                        key={p}
                        onClick={() => setEditPriority(p)}
                        className="rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors"
                        style={{
                          background:
                            editPriority === p
                              ? PRIORITY_COLORS[p].bg
                              : 'transparent',
                          color:
                            editPriority === p
                              ? PRIORITY_COLORS[p].text
                              : 'var(--secondary-text)',
                        }}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                  {/* Date picker */}
                  <div className="flex items-center gap-1">
                    <Calendar className="size-3.5" style={{ color: 'var(--secondary-text)' }} />
                    <input
                      type="date"
                      value={editDueDate}
                      onChange={(e) => setEditDueDate(e.target.value)}
                      className="rounded border px-2 py-1 text-xs"
                      style={{
                        borderColor: 'var(--subtle-border)',
                        color: 'var(--body-text)',
                        background: 'var(--page-bg)',
                      }}
                    />
                  </div>
                </>
              ) : (
                <>
                  {/* Priority badge */}
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-0.5 capitalize"
                    style={{
                      fontSize: '12px',
                      fontWeight: 500,
                      background: PRIORITY_COLORS[currentTask.priority].bg,
                      color: PRIORITY_COLORS[currentTask.priority].text,
                    }}
                  >
                    {currentTask.priority}
                  </span>
                  {/* Due date */}
                  {currentTask.due_date && (
                    <span
                      className="inline-flex items-center gap-1"
                      style={{
                        fontSize: '13px',
                        color: 'var(--secondary-text)',
                      }}
                    >
                      <Calendar className="size-3.5" />
                      {format(new Date(currentTask.due_date), 'MMM d, yyyy')}
                    </span>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Edit save/cancel bar */}
          {store.isEditing && (
            <div className="flex items-center gap-2 mt-4">
              <button
                onClick={handleEditSave}
                className="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
                style={{
                  background: 'var(--brand-coral)',
                  color: 'white',
                }}
              >
                Save
              </button>
              <button
                onClick={() => store.setEditing(false)}
                className="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
                style={{
                  color: 'var(--secondary-text)',
                }}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Action bar */}
      <div
        className="flex flex-col items-center gap-3 pb-8 pt-4"
        style={{ maxWidth: '560px', width: '100%', margin: '0 auto' }}
      >
        <div className="flex items-center gap-4">
          {/* Dismiss */}
          <button
            onClick={handleDismiss}
            className="flex flex-col items-center gap-1 rounded-xl px-5 py-3 transition-colors"
            style={{
              border: '1px solid var(--subtle-border)',
              background: 'var(--card-bg)',
              color: 'var(--body-text)',
              minWidth: '90px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)'
              e.currentTarget.style.background = 'rgba(239,68,68,0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--subtle-border)'
              e.currentTarget.style.background = 'var(--card-bg)'
            }}
          >
            <X className="size-5" />
            <span style={{ fontSize: '13px', fontWeight: 500 }}>Dismiss</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 400,
                color: 'var(--secondary-text)',
              }}
            >
              &larr; key
            </span>
          </button>

          {/* Later */}
          <button
            onClick={handleLater}
            className="flex flex-col items-center gap-1 rounded-xl px-5 py-3 transition-colors"
            style={{
              border: '1px solid var(--subtle-border)',
              background: 'var(--card-bg)',
              color: 'var(--body-text)',
              minWidth: '90px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'rgba(245,158,11,0.3)'
              e.currentTarget.style.background = 'rgba(245,158,11,0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--subtle-border)'
              e.currentTarget.style.background = 'var(--card-bg)'
            }}
          >
            <Clock className="size-5" />
            <span style={{ fontSize: '13px', fontWeight: 500 }}>Later</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 400,
                color: 'var(--secondary-text)',
              }}
            >
              &darr; key
            </span>
          </button>

          {/* Confirm */}
          <button
            onClick={handleConfirm}
            className="flex flex-col items-center gap-1 rounded-xl px-6 py-3 transition-colors"
            style={{
              background: 'var(--brand-coral)',
              color: 'white',
              border: '1px solid transparent',
              minWidth: '100px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = '0.9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = '1'
            }}
          >
            <CheckCircle className="size-5" />
            <span style={{ fontSize: '13px', fontWeight: 500 }}>Confirm</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 400,
                color: 'rgba(255,255,255,0.7)',
              }}
            >
              &rarr; key
            </span>
          </button>
        </div>

        {/* Edit link */}
        {!store.isEditing && (
          <button
            onClick={() => store.setEditing(true)}
            className="transition-colors"
            style={{
              fontSize: '14px',
              fontWeight: 400,
              color: 'var(--brand-coral)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Edit before confirming
          </button>
        )}
      </div>
    </div>
  )
}
