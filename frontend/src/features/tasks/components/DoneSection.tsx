import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { formatDistanceToNow, isAfter, subDays } from 'date-fns'
import { useTasks } from '../hooks/useTasks'
import type { Task } from '../types/tasks'

interface DoneSectionProps {
  searchFilter?: string
}

export function DoneSection({ searchFilter }: DoneSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { data } = useTasks()

  const sevenDaysAgo = subDays(new Date(), 7)

  const doneTasks = (data?.tasks ?? [])
    .filter(
      (t: Task) =>
        t.status === 'done' &&
        isAfter(new Date(t.completed_at || t.updated_at), sevenDaysAgo) &&
        (!searchFilter || t.title.toLowerCase().includes(searchFilter.toLowerCase()))
    )
    .sort((a: Task, b: Task) => {
      const aDate = new Date(a.completed_at || a.updated_at)
      const bDate = new Date(b.completed_at || b.updated_at)
      return bDate.getTime() - aDate.getTime()
    })

  if (doneTasks.length === 0) return null

  return (
    <section>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full hover:opacity-80 transition-opacity"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px 0',
          marginBottom: isExpanded ? '12px' : '0',
        }}
      >
        <ChevronRight
          className="size-4 transition-transform"
          style={{
            color: 'var(--secondary-text)',
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
            transitionDuration: '200ms',
          }}
        />
        <span
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--heading-text)',
          }}
        >
          Done (last 7 days)
        </span>
        <span
          style={{
            fontSize: '14px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
          }}
        >
          ({doneTasks.length})
        </span>
      </button>

      {/* Expandable content */}
      <div
        style={{
          maxHeight: isExpanded ? `${doneTasks.length * 60 + 40}px` : '0px',
          overflow: 'hidden',
          transition: 'max-height 200ms ease-in-out',
        }}
      >
        <div className="flex flex-col">
          {doneTasks.map((task: Task) => (
            <div
              key={task.id}
              className="flex items-center justify-between"
              style={{
                padding: '10px 16px',
                borderBottom: '1px solid var(--subtle-border)',
              }}
            >
              <span
                style={{
                  fontSize: '14px',
                  fontWeight: 400,
                  color: 'var(--secondary-text)',
                  textDecoration: 'line-through',
                  flex: 1,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {task.title}
              </span>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 400,
                  color: 'var(--secondary-text)',
                  marginLeft: '16px',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                Completed{' '}
                {formatDistanceToNow(
                  new Date(task.completed_at || task.updated_at),
                  { addSuffix: true }
                )}
              </span>
              {Boolean(task.metadata?.generated_output) && (
                <a
                  href={String(task.metadata?.generated_output)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: '12px',
                    color: 'var(--brand-coral)',
                    marginLeft: '12px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  View output
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
