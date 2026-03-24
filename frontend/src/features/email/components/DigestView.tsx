import { Inbox } from 'lucide-react'
import { colors, typography } from '@/lib/design-tokens'
import { useDailyDigest } from '../hooks/useDailyDigest'
import { useEmailStore } from '../store/emailStore'
import type { DigestThread } from '../types/email'

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function groupByCategory(threads: DigestThread[]): Record<string, DigestThread[]> {
  return threads.reduce<Record<string, DigestThread[]>>((acc, thread) => {
    const key = thread.category ?? 'Uncategorized'
    if (!acc[key]) acc[key] = []
    acc[key].push(thread)
    return acc
  }, {})
}

interface DigestRowProps {
  thread: DigestThread
  onClick: (threadId: string) => void
}

function DigestRow({ thread, onClick }: DigestRowProps) {
  return (
    <button
      type="button"
      className="w-full flex items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-[rgba(233,77,53,0.04)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-coral)]"
      onClick={() => onClick(thread.thread_id)}
    >
      <div className="flex-1 min-w-0">
        <p
          className="truncate"
          style={{ fontSize: typography.body.size, color: colors.headingText }}
        >
          {thread.subject ?? '(no subject)'}
        </p>
        <p
          className="truncate"
          style={{ fontSize: typography.caption.size, color: colors.secondaryText }}
        >
          {thread.sender_email}
        </p>
      </div>
      {thread.message_count > 1 && (
        <span
          className="shrink-0 rounded-full px-1.5 py-0.5 text-xs"
          style={{ backgroundColor: 'var(--subtle-border)', color: colors.secondaryText }}
        >
          {thread.message_count}
        </span>
      )}
    </button>
  )
}

export function DigestView() {
  const { data, isLoading } = useDailyDigest()
  const { selectThread } = useEmailStore()

  if (isLoading) {
    return (
      <div
        className="flex flex-col gap-2 p-4"
        style={{ color: colors.secondaryText, fontSize: typography.body.size }}
      >
        Loading digest…
      </div>
    )
  }

  if (!data || data.threads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <Inbox className="size-10" style={{ color: 'var(--subtle-border)' }} />
        <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
          No low-priority emails today
        </p>
      </div>
    )
  }

  const grouped = groupByCategory(data.threads)
  const categories = Object.keys(grouped).sort()

  return (
    <div className="flex flex-col">
      {/* Date header */}
      <div
        className="px-6 py-3 border-b"
        style={{ borderColor: 'var(--subtle-border)' }}
      >
        <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
          {formatDate(data.date)} &middot; {data.total} thread{data.total !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Category groups */}
      <div className="flex flex-col px-4 py-3 gap-4">
        {categories.map((category) => (
          <div key={category} className="flex flex-col gap-1">
            <p
              className="px-3 pb-1"
              style={{
                fontSize: typography.caption.size,
                fontWeight: '600',
                color: colors.secondaryText,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {category}
            </p>
            {grouped[category].map((thread) => (
              <DigestRow key={thread.thread_id} thread={thread} onClick={selectThread} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
