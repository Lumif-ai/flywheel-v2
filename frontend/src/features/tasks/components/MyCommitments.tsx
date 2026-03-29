import { Target } from 'lucide-react'
import { useTasks } from '../hooks/useTasks'
import { groupTasksByDueDate } from '../types/tasks'
import type { Task, GroupedTasks } from '../types/tasks'
import { TaskSectionHeader } from './TaskSectionHeader'
import { TaskCommitmentCard } from './TaskCommitmentCard'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

interface MyCommitmentsProps {
  onSelect: (id: string) => void
}

const GROUP_ORDER: { key: keyof GroupedTasks; label: string }[] = [
  { key: 'overdue', label: 'OVERDUE' },
  { key: 'today', label: 'TODAY' },
  { key: 'thisWeek', label: 'THIS WEEK' },
  { key: 'nextWeek', label: 'NEXT WEEK' },
  { key: 'later', label: 'LATER' },
]

const COMMITMENT_STATUSES = new Set(['confirmed', 'in_progress', 'blocked'])

export function MyCommitments({ onSelect }: MyCommitmentsProps) {
  const { data, isLoading } = useTasks()

  if (isLoading) {
    return (
      <section>
        <TaskSectionHeader title="My Commitments" count={0} />
        <div className="flex flex-col gap-4">
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      </section>
    )
  }

  const filteredTasks = (data?.tasks ?? []).filter(
    (t: Task) => t.commitment_direction === 'yours' && COMMITMENT_STATUSES.has(t.status)
  )

  if (filteredTasks.length === 0) {
    return (
      <section>
        <TaskSectionHeader title="My Commitments" count={0} />
        <EmptyState
          icon={Target}
          title="No active commitments"
          description="Confirmed tasks assigned to you will appear here, grouped by due date."
        />
      </section>
    )
  }

  const groups = groupTasksByDueDate(filteredTasks)

  return (
    <section>
      <TaskSectionHeader title="My Commitments" count={filteredTasks.length} />
      <div className="flex flex-col gap-6">
        {GROUP_ORDER.map(({ key, label }) => {
          const groupTasks = groups[key]
          if (groupTasks.length === 0) return null

          return (
            <div key={key}>
              {/* Group label */}
              <div
                className="flex items-center gap-2"
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                  color: key === 'overdue' ? 'var(--task-overdue-text)' : 'var(--secondary-text)',
                  marginBottom: '12px',
                }}
              >
                <span>{label}</span>
                <span style={{ fontWeight: 400 }}>({groupTasks.length})</span>
              </div>

              {/* Task cards */}
              <div className="flex flex-col gap-3">
                {groupTasks.map((task: Task) => (
                  <TaskCommitmentCard
                    key={task.id}
                    task={task}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
