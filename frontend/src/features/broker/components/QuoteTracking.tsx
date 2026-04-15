import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Clock, CheckCircle, AlertTriangle, Mail, FileText, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { format, differenceInDays } from 'date-fns'
import {
  useBrokerQuotes,
  useMarkReceived,
  useManualQuoteEntry,
  useDraftFollowups,
} from '../hooks/useBrokerQuotes'
import type { CarrierQuote, ManualQuotePayload } from '../types/broker'
import { RunInClaudeCodeButton } from './shared/RunInClaudeCodeButton'

interface QuoteTrackingProps {
  projectId: string
}

type QuoteDisplayStatus = 'pending' | 'solicited' | 'received' | 'extracting' | 'extracted' | 'needs_follow_up'

function formatCurrency(val: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
}

function getDisplayStatus(quote: CarrierQuote): QuoteDisplayStatus {
  if (quote.status === 'solicited' && quote.solicited_at) {
    const daysSinceSolicited = differenceInDays(new Date(), new Date(quote.solicited_at))
    if (daysSinceSolicited > 7) return 'needs_follow_up'
  }
  return quote.status as QuoteDisplayStatus
}

function StatusIcon({ status }: { status: QuoteDisplayStatus }) {
  switch (status) {
    case 'pending':
      return <Clock className="h-4 w-4 text-gray-400" />
    case 'solicited':
      return <Mail className="h-4 w-4 text-blue-500" />
    case 'received':
      return <FileText className="h-4 w-4 text-green-500" />
    case 'extracting':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
    case 'extracted':
      return <CheckCircle className="h-4 w-4 text-emerald-500" />
    case 'needs_follow_up':
      return <AlertTriangle className="h-4 w-4 text-orange-500" />
  }
}

function statusBadgeVariant(status: QuoteDisplayStatus): string {
  switch (status) {
    case 'pending': return 'bg-gray-100 text-gray-700'
    case 'solicited': return 'bg-blue-100 text-blue-700'
    case 'received': return 'bg-green-100 text-green-700'
    case 'extracting': return 'bg-blue-100 text-blue-700'
    case 'extracted': return 'bg-emerald-100 text-emerald-700'
    case 'needs_follow_up': return 'bg-orange-100 text-orange-700'
  }
}

function statusLabel(status: QuoteDisplayStatus): string {
  switch (status) {
    case 'pending': return 'Pending'
    case 'solicited': return 'Solicited'
    case 'received': return 'Received'
    case 'extracting': return 'Extracting...'
    case 'extracted': return 'Extracted'
    case 'needs_follow_up': return 'Needs Follow-up'
  }
}

function ManualEntryForm({ quoteId, projectId, onClose }: { quoteId: string; projectId: string; onClose: () => void }) {
  const manualEntry = useManualQuoteEntry(projectId)
  const [form, setForm] = useState<ManualQuotePayload>({
    premium: null,
    deductible: null,
    limit_amount: null,
    exclusions: [],
    coverage_id: null,
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    manualEntry.mutate({ quoteId, payload: form }, { onSuccess: onClose })
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 p-3 rounded-lg border bg-gray-50 space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-muted-foreground">Premium</label>
          <input
            type="number"
            className="w-full px-2 py-1 text-sm border rounded"
            placeholder="0.00"
            onChange={(e) => setForm({ ...form, premium: e.target.value ? Number(e.target.value) : null })}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Deductible</label>
          <input
            type="number"
            className="w-full px-2 py-1 text-sm border rounded"
            placeholder="0.00"
            onChange={(e) => setForm({ ...form, deductible: e.target.value ? Number(e.target.value) : null })}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Limit</label>
          <input
            type="number"
            className="w-full px-2 py-1 text-sm border rounded"
            placeholder="0.00"
            onChange={(e) => setForm({ ...form, limit_amount: e.target.value ? Number(e.target.value) : null })}
          />
        </div>
      </div>
      <div>
        <label className="text-xs text-muted-foreground">Exclusions (comma-separated)</label>
        <input
          type="text"
          className="w-full px-2 py-1 text-sm border rounded"
          placeholder="e.g. flood, earthquake"
          onChange={(e) => setForm({ ...form, exclusions: e.target.value ? e.target.value.split(',').map((s) => s.trim()) : [] })}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={manualEntry.isPending}>
          {manualEntry.isPending ? 'Saving...' : 'Save'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

interface QuoteRowProps {
  quote: CarrierQuote
  projectId: string
  isExpanded: boolean
  onToggleExpand: () => void
}

function QuoteRow({ quote, projectId, isExpanded, onToggleExpand }: QuoteRowProps) {
  const [showManual, setShowManual] = useState(false)
  const markReceivedMutation = useMarkReceived(projectId)
  const displayStatus = getDisplayStatus(quote)

  return (
    <div className="border rounded-lg p-3 space-y-2">
      {/* Row header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <StatusIcon status={displayStatus} />
          <span className="font-medium text-sm">{quote.carrier_name}</span>
          {/* QUOT-02: carrier_type badge */}
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
            quote.carrier_type === 'insurance'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-purple-100 text-purple-700'
          }`}>
            {quote.carrier_type === 'insurance' ? 'Insurance' : 'Surety'}
          </span>
          <Badge className={`text-xs ${statusBadgeVariant(displayStatus)}`}>
            {statusLabel(displayStatus)}
          </Badge>
          {/* QUOT-02: premium when extracted */}
          {displayStatus === 'extracted' && quote.premium != null && (
            <span className="text-sm font-semibold text-emerald-700">
              {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(quote.premium)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {quote.solicited_at && (
              <span>Solicited {format(new Date(quote.solicited_at), 'MMM d')}</span>
            )}
            {quote.received_at && (
              <span>Received {format(new Date(quote.received_at), 'MMM d')}</span>
            )}
          </div>
          {/* QUOT-03: expand/collapse chevron */}
          <button
            onClick={onToggleExpand}
            className="p-0.5 rounded hover:bg-gray-100 text-muted-foreground"
            aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
          >
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Actions based on status */}
      <div className="flex items-center gap-2">
        {(displayStatus === 'solicited' || displayStatus === 'needs_follow_up') ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => markReceivedMutation.mutate(quote.id)}
            disabled={markReceivedMutation.isPending}
          >
            Mark as Received
          </Button>
        ) : null}

        {displayStatus === 'received' && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowManual(!showManual)}
          >
            {showManual ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
            Enter Manually
          </Button>
        )}

        {displayStatus === 'extracting' && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Extracting...
          </span>
        )}

        {displayStatus === 'extracted' && (
          <span className="text-xs text-emerald-600 flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            View in comparison
          </span>
        )}
      </div>

      {showManual && (
        <ManualEntryForm quoteId={quote.id} projectId={projectId} onClose={() => setShowManual(false)} />
      )}

      {/* QUOT-03: Expandable detail panel */}
      {isExpanded && (
        <div className="mt-2 pt-2 border-t space-y-1.5 text-xs text-muted-foreground">
          {quote.deductible != null && (
            <div className="flex justify-between">
              <span>Deductible</span>
              <span className="font-medium text-foreground">{formatCurrency(quote.deductible)}</span>
            </div>
          )}
          {quote.limit_amount != null && (
            <div className="flex justify-between">
              <span>Limit</span>
              <span className="font-medium text-foreground">{formatCurrency(quote.limit_amount)}</span>
            </div>
          )}
          {quote.exclusions.length > 0 && (
            <div>
              <span>Exclusions: </span>
              <span className="font-medium text-foreground">{quote.exclusions.join(', ')}</span>
            </div>
          )}
          {quote.documents.length > 0 && (
            <div>
              <span>Source: </span>
              <span className="font-medium text-foreground">{quote.documents[0]?.display_name ?? '—'}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function QuoteTracking({ projectId }: QuoteTrackingProps) {
  const { data: quotes, isLoading } = useBrokerQuotes(projectId)
  const followupsMutation = useDraftFollowups(projectId)
  const [expandedQuoteId, setExpandedQuoteId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    )
  }

  if (!quotes || quotes.length === 0) return null

  // QUOT-01: Summary badge counts
  const received = quotes.filter(q => ['received', 'extracting', 'extracted'].includes(q.status)).length
  const pending = quotes.filter(q => ['solicited', 'pending'].includes(q.status)).length

  // QUOT-04: Show single RunInClaudeCodeButton when any quote is in 'received' status
  const hasReceived = quotes.some(q => q.status === 'received')

  // QUOT-05: Completion card when all quotes are extracted/received
  const allExtracted = quotes.length > 0 && quotes.every(q => ['extracted', 'received'].includes(q.status))

  const hasSolicited = quotes.some((q) => q.status === 'solicited')

  return (
    <div className="space-y-4">
      {/* Header with QUOT-01 summary badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="text-lg font-medium">Quote Tracking</h3>
        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-700 px-2.5 py-0.5 text-xs font-medium">
          {received} of {quotes.length} received
        </span>
        {pending > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 text-orange-700 px-2.5 py-0.5 text-xs font-medium">
            <span className="animate-pulse inline-block w-1.5 h-1.5 rounded-full bg-orange-500" />
            {pending} pending
          </span>
        )}
      </div>

      {/* QUOT-04: Single RunInClaudeCodeButton */}
      {hasReceived && (
        <RunInClaudeCodeButton
          command={`claude "Extract quotes for project ${projectId}"`}
          label="Extract & Compare Quotes"
          variant="prominent"
          description="Runs Claude Code to extract premium data from quote documents"
        />
      )}

      {/* Quote rows */}
      <div className="space-y-2">
        {quotes.map((quote) => (
          <QuoteRow
            key={quote.id}
            quote={quote}
            projectId={projectId}
            isExpanded={expandedQuoteId === quote.id}
            onToggleExpand={() => setExpandedQuoteId(id => id === quote.id ? null : quote.id)}
          />
        ))}
      </div>

      {/* QUOT-05: Completion card (replaces Draft Follow-ups when all extracted) */}
      {allExtracted ? (
        <div className="rounded-lg bg-green-50 border border-green-200 p-4 flex items-center gap-3 text-green-700">
          <CheckCircle className="h-5 w-5 shrink-0" />
          <div>
            <p className="text-sm font-medium">All quotes received</p>
            <p className="text-xs text-green-600">View the comparison matrix to finalize your recommendation.</p>
          </div>
        </div>
      ) : (
        hasSolicited && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => followupsMutation.mutate()}
            disabled={followupsMutation.isPending}
          >
            <Mail className="h-4 w-4 mr-1" />
            Draft Follow-ups
          </Button>
        )
      )}
    </div>
  )
}
