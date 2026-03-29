import { useCallback } from 'react'
import { CheckCircle } from 'lucide-react'
import { toast } from 'sonner'
import { useTasks } from '../hooks/useTasks'
import { useUpdateTaskStatus } from '../hooks/useUpdateTaskStatus'
import { TaskSectionHeader } from './TaskSectionHeader'
import { TaskTriageCard } from './TaskTriageCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { staggerDelay } from '@/lib/animations'
import type { Task, TaskStatus } from '../types/tasks'

const TRIAGE_STATUSES: Set<TaskStatus> = new Set(['detected', 'in_review', 'deferred'])

const PRIORITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

function TriageSkeleton() {
  return (
    <div
      className="flex items-center justify-between"
      style={{
        padding: '16px 20px',
        background: 'var(--card-bg)',
        border: '1px solid var(--subtle-border)',
        borderRadius: '12px',
      }}
    >
      <div className="flex flex-col gap-2 flex-1">
        <Skeleton className="h-4 w-3/5" />
        <Skeleton className="h-3 w-2/5" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="size-7 rounded-md" />
        <Skeleton className="size-7 rounded-md" />
        <Skeleton className="size-7 rounded-md" />
      </div>
    </div>
  )
}

export function TriageInbox() {
  const { data, isLoading } = useTasks()
  const statusMutation = useUpdateTaskStatus()

  // Filter to triage-eligible tasks, sorted by priority then created_at
  const triageTasks = (data?.tasks ?? [])
    .filter((t) => TRIAGE_STATUSES.has(t.status))
    .sort((a, b) => {
      const priDiff = (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1)
      if (priDiff !== 0) return priDiff
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  const handleAction = useCallback(
    (task: Task, newStatus: TaskStatus, label: string) => {
      statusMutation.mutate(
        { id: task.id, status: newStatus },
        {
          onSuccess: () => {
            toast(label, {
              action: {
                label: 'Undo',
                onClick: () => statusMutation.mutate({ id: task.id, status: task.status }),
              },
              duration: 5000,
            })
          },
        },
      )
    },
    [statusMutation],
  )

  const handleConfirm = useCallback(
    (task: Task) => handleAction(task, 'confirmed', 'Task confirmed'),
    [handleAction],
  )

  const handleDismiss = useCallback(
    (task: Task) => handleAction(task, 'dismissed', 'Task dismissed'),
    [handleAction],
  )

  const handleLater = useCallback(
    (task: Task) => handleAction(task, 'deferred', 'Task saved for later'),
    [handleAction],
  )

  return (
    <section>
      <TaskSectionHeader
        title="Triage Inbox"
        count={triageTasks.length}
        action={
          <Button variant="ghost" size="sm" disabled>
            Review All &rarr;
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex flex-col gap-3" role="list">
          <TriageSkeleton />
          <TriageSkeleton />
          <TriageSkeleton />
        </div>
      ) : triageTasks.length === 0 ? (
        <div
          className="flex items-center justify-center gap-2 py-8"
          style={{ color: 'var(--secondary-text)', fontSize: '14px' }}
        >
          <CheckCircle className="size-5" />
          <span>All caught up</span>
        </div>
      ) : (
        <div className="flex flex-col gap-3" role="list">
          {triageTasks.map((task, index) => (
            <TaskTriageCard
              key={task.id}
              task={task}
              onConfirm={handleConfirm}
              onLater={handleLater}
              onDismiss={handleDismiss}
              style={{
                animationDelay: staggerDelay(index),
                opacity: 0,
                animation: `fade-slide-up 200ms ease-out ${staggerDelay(index)} forwards`,
              }}
            />
          ))}
        </div>
      )}
    </section>
  )
}
