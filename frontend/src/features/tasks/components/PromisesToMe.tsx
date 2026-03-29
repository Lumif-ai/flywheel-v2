import { useState } from 'react'
import { Handshake } from 'lucide-react'
import { isBefore, startOfDay } from 'date-fns'
import { toast } from 'sonner'
import { useTasks } from '../hooks/useTasks'
import { useCreateTask } from '../hooks/useCreateTask'
import { TaskSectionHeader } from './TaskSectionHeader'
import { TaskWatchlistItem } from './TaskWatchlistItem'
import { BrandedCard } from '@/components/ui/branded-card'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { animationClasses, staggerDelay } from '@/lib/animations'
import type { Task } from '../types/tasks'

const EXCLUDED_STATUSES = new Set(['done', 'dismissed'])
const PROMISE_DIRECTIONS = new Set(['theirs', 'mutual'])

interface PromisesToMeProps {
  searchFilter?: string
}

export function PromisesToMe({ searchFilter }: PromisesToMeProps) {
  const { data, isLoading } = useTasks()
  const createTask = useCreateTask()
  const [followUpCreated, setFollowUpCreated] = useState<Set<string>>(new Set())

  if (isLoading) {
    return (
      <section>
        <TaskSectionHeader title="Promises to Me" count={0} />
        <div className="flex flex-col gap-0">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl mt-1" />
        </div>
      </section>
    )
  }

  const promises = (data?.tasks ?? [])
    .filter(
      (t: Task) =>
        PROMISE_DIRECTIONS.has(t.commitment_direction) &&
        !EXCLUDED_STATUSES.has(t.status) &&
        (!searchFilter || t.title.toLowerCase().includes(searchFilter.toLowerCase()))
    )
    .sort((a: Task, b: Task) => {
      // Overdue items first
      const now = startOfDay(new Date())
      const aOverdue = a.due_date && isBefore(startOfDay(new Date(a.due_date)), now)
      const bOverdue = b.due_date && isBefore(startOfDay(new Date(b.due_date)), now)
      if (aOverdue && !bOverdue) return -1
      if (!aOverdue && bOverdue) return 1
      // Then by created_at DESC
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  if (promises.length === 0) {
    return (
      <section>
        <TaskSectionHeader title="Promises to Me" count={0} />
        {searchFilter ? (
          <p
            style={{
              fontSize: '14px',
              color: 'var(--secondary-text)',
              padding: '16px 0',
              textAlign: 'center',
            }}
          >
            No tasks matching &lsquo;{searchFilter}&rsquo;
          </p>
        ) : (
          <EmptyState
            icon={Handshake}
            title="No outstanding promises"
            description="Commitments others have made to you will appear here for tracking."
          />
        )}
      </section>
    )
  }

  const handleCreateFollowUp = (task: Task) => {
    const contextLabel = task.meeting_id ? 'meeting contact' : task.title.split(' ').slice(0, 3).join(' ')

    createTask.mutate(
      {
        title: `Follow up with ${contextLabel} re: ${task.title}`,
        commitment_direction: 'yours',
        account_id: task.account_id ?? undefined,
        task_type: 'followup',
        priority: 'medium',
      },
      {
        onSuccess: () => {
          setFollowUpCreated((prev) => new Set(prev).add(task.id))
          toast.success('Follow-up task created')
        },
      }
    )
  }

  return (
    <section>
      <TaskSectionHeader title="Promises to Me" count={promises.length} />
      <BrandedCard variant="info" hoverable={false} className="!p-0 overflow-hidden">
        <div
          className="divide-y"
          style={{ borderColor: 'var(--subtle-border)' }}
        >
          {promises.map((task: Task, index: number) => (
            <div
              key={task.id}
              className={animationClasses.fadeSlideUp}
              style={{ animationDelay: staggerDelay(index) }}
            >
              <TaskWatchlistItem
                task={task}
                onCreateFollowUp={handleCreateFollowUp}
                hasFollowUp={followUpCreated.has(task.id)}
              />
            </div>
          ))}
        </div>
      </BrandedCard>
    </section>
  )
}
