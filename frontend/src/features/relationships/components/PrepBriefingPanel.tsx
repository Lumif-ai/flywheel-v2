import { Loader2, BookOpen, RefreshCw, AlertCircle } from 'lucide-react'
import { useRelationshipPrep } from '../hooks/useRelationshipPrep'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PrepBriefingPanelProps {
  accountId: string
  accountName: string
  meetingId?: string
}

// ---------------------------------------------------------------------------
// PrepBriefingPanel
// ---------------------------------------------------------------------------

export function PrepBriefingPanel({ accountId, accountName, meetingId }: PrepBriefingPanelProps) {
  const { phase, status, briefingHtml, error, startPrep, reset } = useRelationshipPrep(accountId)

  // ---- Idle: just a button ----
  if (phase === 'idle') {
    return (
      <div className="mb-4">
        <button
          onClick={() => startPrep(meetingId)}
          className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium transition-opacity hover:opacity-85"
          style={{ background: 'var(--brand-coral)', color: '#fff' }}
        >
          <BookOpen className="size-4" />
          Prep for Meeting
        </button>
      </div>
    )
  }

  // ---- Running: spinner + stage message ----
  if (phase === 'running') {
    return (
      <div
        className="rounded-xl p-5 mb-4 flex items-center gap-3"
        style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.2)' }}
      >
        <Loader2 className="size-5 animate-spin shrink-0" style={{ color: '#3B82F6' }} />
        <div>
          <p className="text-sm font-medium" style={{ color: '#2563eb' }}>
            Preparing briefing for {accountName}…
          </p>
          {status && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>
              {status}
            </p>
          )}
        </div>
      </div>
    )
  }

  // ---- Error: red card with retry ----
  if (phase === 'error') {
    return (
      <div
        className="rounded-xl p-5 mb-4 flex items-center justify-between gap-3"
        style={{ background: 'rgba(220,38,38,0.05)', border: '1px solid rgba(220,38,38,0.2)' }}
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="size-5 shrink-0" style={{ color: '#dc2626' }} />
          <p className="text-sm font-medium" style={{ color: '#dc2626' }}>
            {error ?? 'Prep failed — please try again'}
          </p>
        </div>
        <button
          onClick={() => { reset(); startPrep(meetingId) }}
          className="text-sm px-4 py-1.5 rounded-lg font-medium shrink-0 transition-opacity hover:opacity-80"
          style={{ background: 'rgba(220,38,38,0.1)', color: '#dc2626' }}
        >
          Retry
        </button>
      </div>
    )
  }

  // ---- Done: render briefing HTML + regenerate button ----
  return (
    <div
      className="rounded-xl mb-4 overflow-hidden"
      style={{ border: '1px solid var(--subtle-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
    >
      {/* Header row */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ background: 'var(--brand-light)', borderBottom: '1px solid rgba(233,77,53,0.15)' }}
      >
        <div className="flex items-center gap-2">
          <BookOpen className="size-4" style={{ color: 'var(--brand-coral)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--heading-text)' }}>
            Meeting Prep: {accountName}
          </span>
        </div>
        <button
          onClick={() => startPrep(meetingId)}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-80"
          style={{ background: 'rgba(233,77,53,0.1)', color: 'var(--brand-coral)' }}
        >
          <RefreshCw className="size-3" />
          Regenerate
        </button>
      </div>

      {/* Briefing HTML */}
      <div
        className="px-5 py-4"
        style={{ background: 'var(--card-bg)' }}
      >
        {briefingHtml ? (
          <div
            className="prose prose-sm max-w-none"
            style={{
              color: 'var(--heading-text)',
              fontSize: '0.875rem',
              lineHeight: '1.6',
            }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: briefingHtml }}
          />
        ) : (
          <p className="text-sm" style={{ color: 'var(--secondary-text)' }}>
            No briefing content available.
          </p>
        )}
      </div>
    </div>
  )
}
