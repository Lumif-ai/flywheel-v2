import { useState, useEffect } from 'react'
import { CheckSquare, Plus, Search, X } from 'lucide-react'
import { useTaskSummary } from '../hooks/useTaskSummary'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { TriageInbox } from './TriageInbox'
import { MyCommitments } from './MyCommitments'
import { PromisesToMe } from './PromisesToMe'
import { DoneSection } from './DoneSection'
import { TaskQuickAdd } from './TaskQuickAdd'
import { TaskDetailPanel } from './TaskDetailPanel'
import { useTaskKeyboardNav } from '../hooks/useTaskKeyboardNav'

export function TasksPage() {
  const { data: summary, isLoading } = useTaskSummary()
  const [showQuickAdd, setShowQuickAdd] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Debounce search input at 300ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Keyboard navigation
  useTaskKeyboardNav({
    enabled: !selectedTaskId && !showQuickAdd,
    onSelect: (id) => setSelectedTaskId(id),
  })

  // Derive counts from summary
  const activeCount = (summary?.confirmed ?? 0) + (summary?.in_progress ?? 0) + (summary?.in_review ?? 0)
  const needReviewCount = (summary?.detected ?? 0) + (summary?.deferred ?? 0)
  const totalAll = summary
    ? summary.detected + summary.in_review + summary.confirmed + summary.in_progress + summary.done + summary.blocked + summary.dismissed + summary.deferred
    : 0
  const isCompletelyEmpty = !isLoading && summary && totalAll === 0

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
      <div
        className="mx-auto px-6 md:px-12"
        style={{
          maxWidth: '960px',
          paddingTop: '48px',
          paddingBottom: '48px',
        }}
      >
        {/* Page header */}
        {isLoading ? (
          <div className="mb-12">
            <Skeleton className="h-8 w-32 mb-2" />
            <Skeleton className="h-4 w-48" />
          </div>
        ) : isCompletelyEmpty ? (
          <EmptyState
            icon={CheckSquare}
            title="No tasks yet"
            description="Tasks will appear here after your meetings are processed"
          />
        ) : (
          <>
            <div className="flex items-start justify-between" style={{ marginBottom: '48px' }}>
              <div>
                <h1
                  style={{
                    fontSize: '28px',
                    fontWeight: 700,
                    lineHeight: '1.2',
                    letterSpacing: '-0.02em',
                    color: 'var(--heading-text)',
                    margin: 0,
                  }}
                >
                  Tasks
                </h1>
                <p
                  style={{
                    fontSize: '13px',
                    fontWeight: 400,
                    lineHeight: '1.4',
                    color: 'var(--secondary-text)',
                    margin: '4px 0 0 0',
                  }}
                >
                  {activeCount} active &middot; {needReviewCount} need review
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div
                  className="flex items-center"
                  style={{
                    background: 'var(--card-bg)',
                    border: '1px solid var(--subtle-border)',
                    borderRadius: '8px',
                    padding: '0 10px',
                    height: '32px',
                    minWidth: '180px',
                  }}
                >
                  <Search
                    className="size-3.5 shrink-0"
                    style={{ color: 'var(--secondary-text)' }}
                  />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search tasks..."
                    className="bg-transparent outline-none flex-1"
                    style={{
                      border: 'none',
                      fontSize: '13px',
                      color: 'var(--body-text)',
                      padding: '0 8px',
                      lineHeight: '32px',
                    }}
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="shrink-0 hover:opacity-80 transition-opacity"
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <X
                        className="size-3.5"
                        style={{ color: 'var(--secondary-text)' }}
                      />
                    </button>
                  )}
                </div>
                <Button variant="default" size="sm" onClick={() => setShowQuickAdd(true)}>
                  <Plus className="size-3.5" data-icon="inline-start" />
                  Add
                </Button>
              </div>
            </div>

            {/* Section slots with 48px gap between them */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '48px' }}>
              <TriageInbox searchFilter={debouncedSearch} />

              {/* Quick-add form above My Commitments */}
              <div>
                <TaskQuickAdd
                  isOpen={showQuickAdd}
                  onClose={() => setShowQuickAdd(false)}
                />
                <MyCommitments onSelect={(id) => setSelectedTaskId(id)} searchFilter={debouncedSearch} />
              </div>

              <PromisesToMe searchFilter={debouncedSearch} />
              <DoneSection searchFilter={debouncedSearch} />
            </div>
          </>
        )}
      </div>

      {/* Detail panel */}
      <TaskDetailPanel
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
      />
    </div>
  )
}
