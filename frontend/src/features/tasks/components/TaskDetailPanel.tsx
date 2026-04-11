import { useState, useRef, useEffect, useCallback } from 'react'
import { NavLink } from 'react-router'
import {
  X,
  Calendar,
  Building2,
  MapPin,
  Zap,
  ArrowUpRight,
  Loader2,
  RefreshCw,
  ExternalLink,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { useTask } from '../hooks/useTask'
import { useUpdateTask } from '../hooks/useUpdateTask'
import { useUpdateTaskStatus } from '../hooks/useUpdateTaskStatus'
import { TaskStatusBadge } from './TaskStatusBadge'
import { TaskSkillChip } from './TaskSkillChip'
import { useSkillExecution } from '../hooks/useSkillExecution'
import { VALID_TRANSITIONS, PRIORITIES } from '../types/tasks'
import type { TaskStatus, Priority } from '../types/tasks'

interface TaskDetailPanelProps {
  taskId: string | null
  onClose: () => void
}

function formatStatusLabel(status: TaskStatus): string {
  return status
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase())
}

export function TaskDetailPanel({ taskId, onClose }: TaskDetailPanelProps) {
  const { data: task, isLoading } = useTask(taskId)
  const updateTask = useUpdateTask()
  const updateStatus = useUpdateTaskStatus()
  const skillExecution = useSkillExecution()

  // Editable title state
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const titleInputRef = useRef<HTMLInputElement>(null)

  // Editable description state
  const [editDescription, setEditDescription] = useState('')
  const [descriptionInitialized, setDescriptionInitialized] = useState(false)
  const descriptionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Editable due date state
  const [isEditingDueDate, setIsEditingDueDate] = useState(false)

  // Sync description when task loads
  useEffect(() => {
    if (task && !descriptionInitialized) {
      setEditDescription(task.description ?? '')
      setDescriptionInitialized(true)
    }
  }, [task, descriptionInitialized])

  // Reset when panel closes
  useEffect(() => {
    if (!taskId) {
      setIsEditingTitle(false)
      setDescriptionInitialized(false)
      setIsEditingDueDate(false)
    }
  }, [taskId])

  // Focus title input when editing
  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select()
    }
  }, [isEditingTitle])

  const handleTitleSave = useCallback(() => {
    if (!task) return
    const trimmed = editTitle.trim()
    if (trimmed && trimmed !== task.title) {
      updateTask.mutate(
        { id: task.id, body: { title: trimmed } },
        {
          onError: () => toast.error('Failed to update title'),
        }
      )
    }
    setIsEditingTitle(false)
  }, [task, editTitle, updateTask])

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleTitleSave()
    } else if (e.key === 'Escape') {
      setEditTitle(task?.title ?? '')
      setIsEditingTitle(false)
    }
  }

  const handleDescriptionBlur = useCallback(() => {
    if (!task) return
    if (descriptionTimerRef.current) clearTimeout(descriptionTimerRef.current)
    descriptionTimerRef.current = setTimeout(() => {
      const trimmed = editDescription.trim()
      if (trimmed !== (task.description ?? '').trim()) {
        updateTask.mutate(
          { id: task.id, body: { description: trimmed || null } },
          {
            onError: () => toast.error('Failed to update description'),
          }
        )
      }
    }, 500)
  }, [task, editDescription, updateTask])

  const handleStatusChange = (newStatus: TaskStatus) => {
    if (!task) return
    updateStatus.mutate(
      { id: task.id, status: newStatus },
      {
        onError: () => toast.error('Failed to update status'),
      }
    )
  }

  const handlePriorityChange = (newPriority: Priority) => {
    if (!task) return
    if (newPriority === task.priority) return
    updateTask.mutate(
      { id: task.id, body: { priority: newPriority } },
      {
        onError: () => toast.error('Failed to update priority'),
      }
    )
  }

  const handleDueDateChange = (dateStr: string) => {
    if (!task) return
    updateTask.mutate(
      { id: task.id, body: { due_date: dateStr || null } },
      {
        onError: () => toast.error('Failed to update due date'),
      }
    )
    setIsEditingDueDate(false)
  }

  const handleMarkComplete = () => {
    if (!task) return
    updateStatus.mutate(
      { id: task.id, status: 'done' },
      {
        onSuccess: () => {
          toast.success('Task completed')
          onClose()
        },
        onError: () => toast.error('Failed to complete task'),
      }
    )
  }

  const handleDismiss = () => {
    if (!task) return
    updateStatus.mutate(
      { id: task.id, status: 'dismissed' },
      {
        onSuccess: () => {
          toast.success('Task dismissed')
          onClose()
        },
        onError: () => toast.error('Failed to dismiss task'),
      }
    )
  }

  const validTransitions = task ? VALID_TRANSITIONS[task.status] : []
  const canComplete = task ? validTransitions.includes('done') : false
  const canDismiss = task ? validTransitions.includes('dismissed') : false

  return (
    <Sheet
      open={!!taskId}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <SheetContent
        side="right"
        className="sm:max-w-[480px] w-full !p-0 flex flex-col"
        showCloseButton={false}
      >
        {isLoading || !task ? (
          <div className="flex-1 flex items-center justify-center">
            <div
              className="animate-pulse"
              style={{ color: 'var(--secondary-text)', fontSize: '14px' }}
            >
              Loading...
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div
              className="flex items-start justify-between gap-3"
              style={{
                padding: '24px 24px 16px',
                borderBottom: '1px solid var(--subtle-border)',
              }}
            >
              <div className="flex-1 min-w-0">
                <SheetTitle className="sr-only">{task.title}</SheetTitle>
                <SheetDescription className="sr-only">
                  Task detail panel for editing and managing this task
                </SheetDescription>
                {isEditingTitle ? (
                  <input
                    ref={titleInputRef}
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={handleTitleSave}
                    onKeyDown={handleTitleKeyDown}
                    className="w-full bg-transparent outline-none"
                    style={{
                      fontSize: '18px',
                      fontWeight: 600,
                      color: 'var(--heading-text)',
                      border: '1px solid var(--brand-coral)',
                      borderRadius: '6px',
                      padding: '4px 8px',
                    }}
                  />
                ) : (
                  <h2
                    className="cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => {
                      setEditTitle(task.title)
                      setIsEditingTitle(true)
                    }}
                    style={{
                      fontSize: '18px',
                      fontWeight: 600,
                      color: 'var(--heading-text)',
                      margin: 0,
                    }}
                  >
                    {task.title}
                  </h2>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onClose}
                className="shrink-0 mt-0.5"
              >
                <X className="size-4" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto" style={{ padding: '0 24px' }}>
              {/* Metadata grid */}
              <div style={{ marginTop: '16px' }}>
                {/* Status */}
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: 'var(--page-bg)',
                  }}
                >
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                    }}
                  >
                    Status
                  </span>
                  <div className="flex items-center gap-2">
                    <TaskStatusBadge status={task.status} />
                    {validTransitions.length > 0 && (
                      <select
                        value=""
                        onChange={(e) => {
                          if (e.target.value) {
                            handleStatusChange(e.target.value as TaskStatus)
                          }
                        }}
                        className="bg-transparent border rounded text-xs cursor-pointer"
                        style={{
                          padding: '2px 6px',
                          borderColor: 'var(--subtle-border)',
                          color: 'var(--body-text)',
                          fontSize: '12px',
                        }}
                      >
                        <option value="">Change...</option>
                        {validTransitions.map((s) => (
                          <option key={s} value={s}>
                            {formatStatusLabel(s)}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>

                {/* Priority */}
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: 'var(--card-bg)',
                  }}
                >
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                    }}
                  >
                    Priority
                  </span>
                  <div className="flex items-center gap-1">
                    {PRIORITIES.map((p) => (
                      <button
                        key={p}
                        onClick={() => handlePriorityChange(p)}
                        className="transition-colors"
                        style={{
                          fontSize: '12px',
                          fontWeight: 500,
                          padding: '4px 12px',
                          borderRadius: '6px',
                          border: 'none',
                          cursor: 'pointer',
                          background:
                            task.priority === p
                              ? p === 'high'
                                ? 'rgba(239,68,68,0.1)'
                                : p === 'medium'
                                  ? 'rgba(245,158,11,0.1)'
                                  : 'rgba(34,197,94,0.1)'
                              : 'transparent',
                          color:
                            task.priority === p
                              ? p === 'high'
                                ? '#EF4444'
                                : p === 'medium'
                                  ? '#D97706'
                                  : '#22C55E'
                              : 'var(--secondary-text)',
                        }}
                      >
                        {p.charAt(0).toUpperCase() + p.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Due Date */}
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: 'var(--page-bg)',
                  }}
                >
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                    }}
                  >
                    Due date
                  </span>
                  {isEditingDueDate ? (
                    <input
                      type="date"
                      defaultValue={task.due_date?.split('T')[0] ?? ''}
                      onChange={(e) => handleDueDateChange(e.target.value)}
                      onBlur={() => setIsEditingDueDate(false)}
                      autoFocus
                      className="bg-transparent border rounded text-sm cursor-pointer"
                      style={{
                        padding: '2px 8px',
                        borderColor: 'var(--subtle-border)',
                        color: 'var(--body-text)',
                      }}
                    />
                  ) : (
                    <button
                      onClick={() => setIsEditingDueDate(true)}
                      className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--body-text)',
                        padding: 0,
                      }}
                    >
                      <Calendar className="size-3.5" style={{ color: 'var(--secondary-text)' }} />
                      {task.due_date
                        ? new Date(task.due_date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })
                        : 'Set date'}
                    </button>
                  )}
                </div>

                {/* Account (read-only) */}
                {task.account_id && (
                  <div
                    className="flex items-center justify-between"
                    style={{
                      padding: '12px 16px',
                      borderRadius: '8px',
                      background: 'var(--card-bg)',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--secondary-text)',
                      }}
                    >
                      Account
                    </span>
                    <NavLink
                      to={`/accounts/${task.account_id}`}
                      className="flex items-center gap-1 hover:opacity-80 transition-opacity"
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--brand-coral)',
                        textDecoration: 'none',
                      }}
                    >
                      <Building2 className="size-3.5" />
                      {task.metadata?.account_name
                        ? String(task.metadata.account_name)
                        : 'View account'}
                      <ArrowUpRight className="size-3" />
                    </NavLink>
                  </div>
                )}

                {/* Source meeting (read-only) */}
                {task.meeting_id && (
                  <div
                    className="flex items-center justify-between"
                    style={{
                      padding: '12px 16px',
                      borderRadius: '8px',
                      background: task.account_id ? 'var(--page-bg)' : 'var(--card-bg)',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--secondary-text)',
                      }}
                    >
                      Source
                    </span>
                    <span
                      className="flex items-center gap-1"
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--body-text)',
                      }}
                    >
                      <MapPin className="size-3.5" style={{ color: 'var(--secondary-text)' }} />
                      Meeting &middot;{' '}
                      {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
                    </span>
                  </div>
                )}

                {/* Task type (read-only) */}
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: 'var(--page-bg)',
                  }}
                >
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                    }}
                  >
                    Type
                  </span>
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--body-text)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {task.task_type}
                  </span>
                </div>

                {/* Commitment direction (read-only) */}
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: 'var(--card-bg)',
                  }}
                >
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                    }}
                  >
                    Direction
                  </span>
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--body-text)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {task.commitment_direction}
                  </span>
                </div>
              </div>

              {/* Description */}
              <div style={{ marginTop: '24px' }}>
                <label
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--secondary-text)',
                    display: 'block',
                    marginBottom: '8px',
                  }}
                >
                  Description
                </label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  onBlur={handleDescriptionBlur}
                  placeholder="Add a description..."
                  className="w-full resize-y"
                  style={{
                    minHeight: '80px',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    color: 'var(--body-text)',
                    background: 'var(--page-bg)',
                    border: '1px solid var(--subtle-border)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    outline: 'none',
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              {/* Skills hidden from user-facing UI */}
              {false && task?.suggested_skill && (
                <div
                  style={{
                    marginTop: '24px',
                    padding: '16px',
                    background: 'var(--page-bg)',
                    borderRadius: '12px',
                  }}
                >
                  <label
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--secondary-text)',
                      display: 'block',
                      marginBottom: '12px',
                    }}
                  >
                    Skill
                  </label>
                  <div className="flex items-center justify-between">
                    <TaskSkillChip skillName={task?.suggested_skill ?? ''} />
                  </div>
                  {task?.skill_context && (
                    <p
                      style={{
                        fontSize: '12px',
                        color: 'var(--secondary-text)',
                        marginTop: '8px',
                        fontFamily: 'monospace',
                        lineHeight: '1.4',
                      }}
                    >
                      {JSON.stringify(task?.skill_context).slice(0, 100)}
                      {JSON.stringify(task?.skill_context).length > 100 ? '...' : ''}
                    </p>
                  )}

                  {/* Generate / Regenerate button */}
                  {(task?.status === 'confirmed' || task?.status === 'in_progress') && (
                    <Button
                      variant="default"
                      size="sm"
                      disabled={skillExecution.isExecuting}
                      onClick={() =>
                        skillExecution.execute(
                          task?.suggested_skill ?? '',
                          task?.skill_context ?? {},
                        )
                      }
                      className="mt-3 w-full"
                    >
                      {skillExecution.isExecuting ? (
                        <>
                          <Loader2 className="size-3.5 animate-spin" data-icon="inline-start" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Zap className="size-3.5" data-icon="inline-start" />
                          {task?.metadata?.generated_output
                            ? 'Regenerate Deliverable'
                            : 'Generate Deliverable'}
                        </>
                      )}
                    </Button>
                  )}

                  {/* Error state with Retry */}
                  {skillExecution.error && (
                    <div
                      className="flex items-center justify-between gap-2"
                      style={{
                        marginTop: '12px',
                        padding: '10px 12px',
                        background: 'rgba(239,68,68,0.06)',
                        borderRadius: '8px',
                        fontSize: '13px',
                        color: '#EF4444',
                      }}
                    >
                      <span>{skillExecution.error}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          skillExecution.execute(
                            task?.suggested_skill ?? '',
                            task?.skill_context ?? {},
                          )
                        }
                        style={{ color: '#EF4444', padding: '2px 8px' }}
                      >
                        <RefreshCw className="size-3" />
                        Retry
                      </Button>
                    </div>
                  )}

                  {/* Success result */}
                  {skillExecution.result && (
                    <div
                      className="flex items-center gap-2"
                      style={{
                        marginTop: '12px',
                        padding: '10px 12px',
                        background: 'rgba(34,197,94,0.06)',
                        borderRadius: '8px',
                        fontSize: '13px',
                        color: '#22C55E',
                      }}
                    >
                      <ExternalLink className="size-3.5 shrink-0" />
                      <a
                        href={`/skills/runs/${skillExecution.result?.run_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#22C55E', fontWeight: 500 }}
                      >
                        View generated output
                      </a>
                    </div>
                  )}

                  {/* Previously generated output from metadata */}
                  {!skillExecution.result &&
                    Boolean(task?.metadata?.generated_output) && (
                      <div
                        style={{
                          marginTop: '12px',
                          fontSize: '13px',
                          color: 'var(--body-text)',
                        }}
                      >
                        <span style={{ fontWeight: 500 }}>Generated Output:</span>{' '}
                        <a
                          href={String(task?.metadata?.generated_output)}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--brand-coral)' }}
                        >
                          View output
                        </a>
                      </div>
                    )}
                </div>
              )}
            </div>

            {/* Actions footer */}
            <div
              className="flex items-center gap-3"
              style={{
                padding: '16px 24px',
                borderTop: '1px solid var(--subtle-border)',
                background: 'var(--card-bg)',
              }}
            >
              <Button
                variant="default"
                size="default"
                onClick={handleMarkComplete}
                disabled={!canComplete}
                className="flex-1"
              >
                Mark Complete
              </Button>
              <Button
                variant="ghost"
                size="default"
                onClick={handleDismiss}
                disabled={!canDismiss}
                style={{
                  color: canDismiss ? 'var(--task-overdue-text)' : undefined,
                }}
              >
                Dismiss
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
