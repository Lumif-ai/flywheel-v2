import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Clock, CheckCircle, AlertTriangle, Mail, FileText, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { format, differenceInDays } from 'date-fns'
import {
  useBrokerQuotes,
  useExtractQuote,
  useMarkReceived,
  useManualQuoteEntry,
  useDraftFollowups,
} from '../hooks/useBrokerQuotes'
import type { CarrierQuote, ManualQuotePayload } from '../types/broker'

interface QuoteTrackingProps {
  projectId: string
}

type QuoteDisplayStatus = 'pending' | 'solicited' | 'received' | 'extracting' | 'extracted' | 'needs_follow_up'

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

function QuoteRow({ quote, projectId }: { quote: CarrierQuote; projectId: string }) {
  const [showManual, setShowManual] = useState(false)
  const extractMutation = useExtractQuote(projectId)
  const markReceivedMutation = useMarkReceived(projectId)
  const displayStatus = getDisplayStatus(quote)

  return (
    <div className="border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon status={displayStatus} />
          <span className="font-medium text-sm">{quote.carrier_name}</span>
          <Badge className={`text-xs ${statusBadgeVariant(displayStatus)}`}>
            {statusLabel(displayStatus)}
          </Badge>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {quote.solicited_at && (
            <span>Solicited {format(new Date(quote.solicited_at), 'MMM d')}</span>
          )}
          {quote.received_at && (
            <span>Received {format(new Date(quote.received_at), 'MMM d')}</span>
          )}
        </div>
      </div>

      {/* Actions based on status */}
      <div className="flex items-center gap-2">
        {displayStatus === 'solicited' || displayStatus === 'needs_follow_up' ? (
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
          <>
            <Button
              size="sm"
              onClick={() => extractMutation.mutate({ quoteId: quote.id })}
              disabled={extractMutation.isPending}
            >
              Extract Quote
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowManual(!showManual)}
            >
              {showManual ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
              Enter Manually
            </Button>
          </>
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
    </div>
  )
}

export function QuoteTracking({ projectId }: QuoteTrackingProps) {
  const { data: quotes, isLoading } = useBrokerQuotes(projectId)
  const followupsMutation = useDraftFollowups(projectId)

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

  const hasSolicited = quotes.some((q) => q.status === 'solicited')

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Quote Tracking</h3>
        {hasSolicited && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => followupsMutation.mutate()}
            disabled={followupsMutation.isPending}
          >
            <Mail className="h-4 w-4 mr-1" />
            Draft Follow-ups
          </Button>
        )}
      </div>

      <div className="space-y-2">
        {quotes.map((quote) => (
          <QuoteRow key={quote.id} quote={quote} projectId={projectId} />
        ))}
      </div>
    </div>
  )
}
