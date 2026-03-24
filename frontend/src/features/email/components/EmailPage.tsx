import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { colors, typography, spacing } from '@/lib/design-tokens'
import { useEmailThreads } from '../hooks/useEmailThreads'
import { useManualSync } from '../hooks/useManualSync'
import { ThreadList } from './ThreadList'
import { ThreadDetail } from './ThreadDetail'
import { DigestView } from './DigestView'

type ViewMode = 'inbox' | 'digest'

const PRIORITY_FILTERS = [
  { label: 'All', value: undefined },
  { label: 'Critical+', value: 90 },
  { label: 'High+', value: 70 },
  { label: 'Medium+', value: 50 },
] as const

export function EmailPage() {
  const [priorityMin, setPriorityMin] = useState<number | undefined>(undefined)
  const [viewMode, setViewMode] = useState<ViewMode>('inbox')
  const { data, isLoading } = useEmailThreads(
    priorityMin != null ? { priority_min: priorityMin } : undefined,
  )
  const syncMutation = useManualSync()

  return (
    <div
      className="flex h-full flex-col"
      style={{ background: colors.pageBg }}
    >
      {/* Top bar */}
      <div
        className="shrink-0 flex items-center justify-between border-b px-6 py-4"
        style={{ borderColor: 'var(--subtle-border)', backgroundColor: 'var(--card-bg)' }}
      >
        <div className="flex items-center gap-4">
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              color: colors.headingText,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
              margin: 0,
            }}
          >
            Email
          </h1>

          {/* Inbox / Digest toggle */}
          <div
            className="flex rounded-lg border overflow-hidden"
            style={{ borderColor: 'var(--subtle-border)' }}
          >
            <button
              type="button"
              onClick={() => setViewMode('inbox')}
              className="px-3 py-1.5 text-sm font-medium transition-colors"
              style={{
                backgroundColor: viewMode === 'inbox' ? 'var(--brand-coral)' : 'var(--card-bg)',
                color: viewMode === 'inbox' ? '#fff' : colors.secondaryText,
              }}
            >
              Inbox
            </button>
            <button
              type="button"
              onClick={() => setViewMode('digest')}
              className="px-3 py-1.5 text-sm font-medium transition-colors"
              style={{
                backgroundColor: viewMode === 'digest' ? 'var(--brand-coral)' : 'var(--card-bg)',
                color: viewMode === 'digest' ? '#fff' : colors.secondaryText,
              }}
            >
              Digest
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Priority filter — only shown in inbox view */}
          {viewMode === 'inbox' && (
            <select
              value={priorityMin ?? ''}
              onChange={(e) =>
                setPriorityMin(e.target.value === '' ? undefined : Number(e.target.value))
              }
              className="rounded-lg border px-3 py-1.5 text-sm outline-none"
              style={{
                borderColor: 'var(--subtle-border)',
                color: colors.headingText,
                backgroundColor: 'var(--card-bg)',
              }}
            >
              {PRIORITY_FILTERS.map((f) => (
                <option key={f.label} value={f.value ?? ''}>
                  {f.label}
                </option>
              ))}
            </select>
          )}

          {/* Sync button */}
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[rgba(0,0,0,0.04)] disabled:opacity-50"
            style={{ borderColor: 'var(--subtle-border)', color: colors.headingText }}
          >
            <RefreshCw
              className={`size-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
            {syncMutation.isPending ? 'Syncing…' : 'Sync'}
          </button>
        </div>
      </div>

      {/* Inbox view */}
      {viewMode === 'inbox' && (
        <>
          {/* Thread count */}
          {!isLoading && data && (
            <div
              className="shrink-0 px-6 py-2"
              style={{ borderBottom: `1px solid var(--subtle-border)` }}
            >
              <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                {data.total} thread{data.total !== 1 ? 's' : ''}
              </span>
            </div>
          )}

          {/* Thread list — must be flex-1 with min-h-0 for virtualization to work */}
          <div
            className="flex-1 min-h-0 mx-auto w-full"
            style={{ maxWidth: spacing.maxGrid }}
          >
            <div className="h-full flex flex-col">
              <ThreadList threads={data?.threads ?? []} loading={isLoading} />
            </div>
          </div>
        </>
      )}

      {/* Digest view */}
      {viewMode === 'digest' && (
        <div
          className="flex-1 min-h-0 overflow-auto mx-auto w-full"
          style={{ maxWidth: spacing.maxGrid }}
        >
          <DigestView />
        </div>
      )}

      {/* Thread detail slide-in panel — visible in both views */}
      <ThreadDetail />
    </div>
  )
}
