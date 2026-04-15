import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { CheckCircle, Mail, Loader2, ChevronDown, ChevronUp, Download } from 'lucide-react'
import { format, differenceInDays } from 'date-fns'
import {
  useBrokerQuotes,
  useMarkReceived,
  useManualQuoteEntry,
  useDraftFollowups,
} from '../hooks/useBrokerQuotes'
import type { CarrierQuote, ManualQuotePayload, SolicitationDocument } from '../types/broker'
import { RunInClaudeCodeButton } from './shared/RunInClaudeCodeButton'
import { CarrierBadge } from './CarrierBadge'

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
    <tr>
      <td colSpan={5} className="px-4 py-3">
        <form onSubmit={handleSubmit} className="p-3 rounded-lg border bg-gray-50 space-y-3">
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
      </td>
    </tr>
  )
}

/** Attachment chip for document files */
function DocumentChip({ doc }: { doc: SolicitationDocument }) {
  const ext = doc.display_name?.split('.').pop()?.toLowerCase() ?? ''
  const isPdf = ext === 'pdf'
  const isSpreadsheet = ['xls', 'xlsx', 'csv'].includes(ext)
  const bgColor = isPdf ? '#EA4335' : isSpreadsheet ? '#16a34a' : '#6B7280'
  const label = isPdf ? 'PDF' : isSpreadsheet ? ext.toUpperCase() : 'DOC'

  return (
    <div className="flex items-center gap-1.5 px-2 py-1.5 rounded border border-gray-200 text-xs bg-white hover:bg-gray-50 transition-colors cursor-pointer">
      <div
        className="flex items-center justify-center rounded-sm flex-shrink-0"
        style={{ width: 16, height: 16, backgroundColor: bgColor }}
      >
        <span style={{ color: 'white', fontSize: 7, fontWeight: 700 }}>{label}</span>
      </div>
      <span className="text-gray-700 truncate max-w-[160px]">{doc.display_name}</span>
      <Download className="h-3 w-3 text-muted-foreground flex-shrink-0 ml-auto" />
    </div>
  )
}

export function QuoteTracking({ projectId }: QuoteTrackingProps) {
  const { data: quotes, isLoading } = useBrokerQuotes(projectId)
  const followupsMutation = useDraftFollowups(projectId)
  const [expandedQuoteId, setExpandedQuoteId] = useState<string | null>(null)
  const [showManualFor, setShowManualFor] = useState<string | null>(null)
  const markReceivedMutation = useMarkReceived(projectId)

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

  const received = quotes.filter(q => ['received', 'extracting', 'extracted'].includes(q.status)).length
  const pending = quotes.filter(q => ['solicited', 'pending'].includes(q.status)).length
  const hasReceived = quotes.some(q => q.status === 'received')
  const allExtracted = quotes.length > 0 && quotes.every(q => ['extracted', 'received'].includes(q.status))
  const hasSolicited = quotes.some((q) => q.status === 'solicited')

  return (
    <div className="space-y-4">
      {/* Header with summary badges */}
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

      {/* Extract button */}
      {hasReceived && (
        <RunInClaudeCodeButton
          command={`claude "Extract quotes for project ${projectId}"`}
          label="Extract & Compare Quotes"
          variant="prominent"
          description="Runs Claude Code to extract premium data from quote documents"
        />
      )}

      {/* Table layout */}
      <div className="rounded-xl border overflow-hidden bg-card">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/30">
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Carrier</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Type</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Status</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Premium</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Received</th>
            </tr>
          </thead>
          <tbody>
            {quotes.map((quote) => {
              const displayStatus = getDisplayStatus(quote)
              const isExpanded = expandedQuoteId === quote.id

              return (
                <>
                  <tr
                    key={quote.id}
                    className={`border-t hover:bg-muted/20 transition-colors cursor-pointer ${isExpanded ? 'bg-muted/10' : ''}`}
                    onClick={() => setExpandedQuoteId(id => id === quote.id ? null : quote.id)}
                  >
                    {/* Carrier with logo */}
                    <td className="px-4 py-3">
                      <CarrierBadge name={quote.carrier_name} className="font-medium text-sm" />
                    </td>

                    {/* Type badge */}
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        quote.carrier_type === 'insurance'
                          ? 'bg-[rgba(233,77,53,0.1)] text-[#E94D35]'
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {quote.carrier_type === 'insurance' ? 'Insurance' : 'Surety'}
                      </span>
                    </td>

                    {/* Status badge */}
                    <td className="px-4 py-3">
                      <Badge className={`text-xs ${statusBadgeVariant(displayStatus)}`}>
                        {displayStatus === 'extracting' && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                        {statusLabel(displayStatus)}
                      </Badge>
                    </td>

                    {/* Premium */}
                    <td className="px-4 py-3">
                      {['extracted', 'received'].includes(displayStatus) && quote.premium != null ? (
                        <span className="text-sm font-bold">{formatCurrency(quote.premium)}</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">---</span>
                      )}
                    </td>

                    {/* Received timing */}
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <span>
                          {quote.received_at
                            ? format(new Date(quote.received_at), 'MMM d')
                            : quote.solicited_at
                              ? `Solicited ${format(new Date(quote.solicited_at), 'MMM d')}`
                              : '---'
                          }
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </div>
                    </td>
                  </tr>

                  {/* Expanded detail row */}
                  {isExpanded && (
                    <tr key={`${quote.id}-detail`} className="bg-muted/5">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="grid grid-cols-2 gap-4">
                          {/* Left: quote details */}
                          <div className="space-y-2 text-xs text-muted-foreground">
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

                            {/* Actions */}
                            <div className="flex items-center gap-2 pt-2">
                              {(displayStatus === 'solicited' || displayStatus === 'needs_follow_up') && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={(e) => { e.stopPropagation(); markReceivedMutation.mutate(quote.id) }}
                                  disabled={markReceivedMutation.isPending}
                                >
                                  Mark as Received
                                </Button>
                              )}
                              {displayStatus === 'received' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={(e) => { e.stopPropagation(); setShowManualFor(showManualFor === quote.id ? null : quote.id) }}
                                >
                                  Enter Manually
                                </Button>
                              )}
                              {displayStatus === 'extracted' && (
                                <span className="text-xs text-emerald-600 flex items-center gap-1">
                                  <CheckCircle className="h-3 w-3" />
                                  View in comparison
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Right: documents */}
                          <div>
                            {quote.documents.length > 0 ? (
                              <div className="space-y-1.5">
                                <p className="text-xs font-medium text-muted-foreground mb-2">Documents</p>
                                {quote.documents.map((doc) => (
                                  <DocumentChip key={doc.file_id} doc={doc} />
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground italic">No documents attached</p>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}

                  {/* Manual entry form row */}
                  {showManualFor === quote.id && (
                    <ManualEntryForm
                      key={`${quote.id}-manual`}
                      quoteId={quote.id}
                      projectId={projectId}
                      onClose={() => setShowManualFor(null)}
                    />
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Completion or follow-up */}
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
