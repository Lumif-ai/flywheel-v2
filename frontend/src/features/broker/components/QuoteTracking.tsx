import { useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { CheckCircle, Mail, Loader2, ChevronDown, ChevronUp, Download, FileText } from 'lucide-react'
import { format, differenceInDays } from 'date-fns'
import { apiUrl } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import {
  useBrokerQuotes,
  useMarkReceived,
  useManualQuoteEntry,
  useDraftFollowups,
} from '../hooks/useBrokerQuotes'
import type { CarrierQuote, ManualQuotePayload, SolicitationDocument, ProjectCoverage } from '../types/broker'
import { RunInClaudeCodeButton } from './shared/RunInClaudeCodeButton'
import { CarrierBadge } from './CarrierBadge'

interface QuoteTrackingProps {
  projectId: string
  coverages: ProjectCoverage[]
}

type QuoteDisplayStatus = 'pending' | 'solicited' | 'received' | 'extracting' | 'extracted' | 'selected' | 'needs_follow_up'

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

/** Determine the aggregate status for a group of quotes from the same carrier */
function getGroupStatus(quotes: CarrierQuote[]): QuoteDisplayStatus {
  const statuses = quotes.map(getDisplayStatus)
  // Priority: needs_follow_up > extracting > solicited > pending > received > extracted > selected
  if (statuses.includes('needs_follow_up')) return 'needs_follow_up'
  if (statuses.includes('extracting')) return 'extracting'
  if (statuses.includes('solicited')) return 'solicited'
  if (statuses.includes('pending')) return 'pending'
  if (statuses.includes('received')) return 'received'
  if (statuses.includes('extracted')) return 'extracted'
  if (statuses.includes('selected')) return 'selected'
  return 'pending'
}

function statusBadgeVariant(status: QuoteDisplayStatus): string {
  switch (status) {
    case 'pending': return 'bg-gray-100 text-gray-700'
    case 'solicited': return 'bg-blue-100 text-blue-700'
    case 'received': return 'bg-green-100 text-green-700'
    case 'extracting': return 'bg-blue-100 text-blue-700'
    case 'extracted': return 'bg-emerald-100 text-emerald-700'
    case 'selected': return 'bg-purple-100 text-purple-700'
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
    case 'selected': return 'Selected'
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

/** Sub-row for individual coverage line items within a carrier group */
function QuoteLineItem({ quote, projectId, showManualFor, setShowManualFor, coverageMap }: {
  quote: CarrierQuote
  projectId: string
  showManualFor: string | null
  setShowManualFor: (id: string | null) => void
  coverageMap: Map<string, ProjectCoverage>
}) {
  const displayStatus = getDisplayStatus(quote)
  const markReceivedMutation = useMarkReceived(projectId)

  return (
    <>
      <tr className="bg-muted/5 border-t border-dashed">
        {/* Coverage name */}
        <td className="pl-12 pr-4 py-2">
          <span className="text-xs font-medium text-gray-700">
            {quote.coverage_id && coverageMap.has(quote.coverage_id)
              ? coverageMap.get(quote.coverage_id)!.display_name || coverageMap.get(quote.coverage_id)!.coverage_type.replace(/_/g, ' ')
              : quote.carrier_type === 'insurance' ? 'Insurance' : 'Surety'
            }
          </span>
        </td>

        {/* Status */}
        <td className="px-4 py-2">
          <Badge className={`text-xs ${statusBadgeVariant(displayStatus)}`}>
            {displayStatus === 'extracting' && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
            {statusLabel(displayStatus)}
          </Badge>
        </td>

        {/* Premium */}
        <td className="px-4 py-2" colSpan={2}>
          <div className="flex items-center gap-3">
            {['extracted', 'received', 'selected'].includes(displayStatus) && quote.premium != null ? (
              <span className="text-sm font-medium">{formatCurrency(quote.premium)}</span>
            ) : (
              <span className="text-sm text-muted-foreground">---</span>
            )}

            {/* Inline details */}
            {quote.deductible != null && (
              <span className="text-xs text-muted-foreground">
                Ded: {formatCurrency(quote.deductible)}
              </span>
            )}
            {quote.limit_amount != null && (
              <span className="text-xs text-muted-foreground">
                Limit: {formatCurrency(quote.limit_amount)}
              </span>
            )}
          </div>
        </td>

        {/* Actions */}
        <td className="px-4 py-2">
          <div className="flex items-center gap-2">
            {(displayStatus === 'solicited' || displayStatus === 'needs_follow_up') && (
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-xs"
                onClick={(e) => { e.stopPropagation(); markReceivedMutation.mutate(quote.id) }}
                disabled={markReceivedMutation.isPending}
              >
                Mark Received
              </Button>
            )}
            {displayStatus === 'received' && (
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-xs"
                onClick={(e) => { e.stopPropagation(); setShowManualFor(showManualFor === quote.id ? null : quote.id) }}
              >
                Enter Manually
              </Button>
            )}
            {(displayStatus === 'extracted' || displayStatus === 'selected') && (
              <span className="text-xs text-emerald-600 flex items-center gap-1">
                <CheckCircle className="h-3 w-3" />
              </span>
            )}
          </div>
        </td>
      </tr>

      {/* Documents row */}
      {quote.documents.length > 0 && (
        <tr className="bg-muted/5">
          <td colSpan={5} className="pl-12 pr-4 py-1.5">
            <div className="flex gap-2 flex-wrap">
              {quote.documents.map((doc) => (
                <DocumentChip key={doc.file_id} doc={doc} />
              ))}
            </div>
          </td>
        </tr>
      )}

      {/* Source document link */}
      {quote.source_document_id && (
        <tr className="bg-muted/5">
          <td colSpan={5} className="pl-12 pr-4 py-1.5">
            <div className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Source:</span>
              <a
                href={apiUrl(`/api/v1/files/${quote.source_document_id}/download`)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[#E94D35] hover:underline flex items-center gap-1"
                onClick={async (e) => {
                  e.preventDefault()
                  try {
                    const token = useAuthStore.getState().token
                    const res = await fetch(apiUrl(`/api/v1/files/${quote.source_document_id}/download`), {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
                    })
                    if (res.ok) {
                      const data = await res.json()
                      if (data.download_url) window.open(data.download_url, '_blank')
                    }
                  } catch {
                    // Fallback: show filename only
                  }
                }}
              >
                {quote.source_document_filename || 'View Document'}
                <Download className="h-3 w-3" />
              </a>
            </div>
          </td>
        </tr>
      )}

      {/* Manual entry form */}
      {showManualFor === quote.id && (
        <ManualEntryForm
          quoteId={quote.id}
          projectId={projectId}
          onClose={() => setShowManualFor(null)}
        />
      )}
    </>
  )
}

interface CarrierGroup {
  key: string
  carrierName: string
  carrierType: string
  quotes: CarrierQuote[]
  totalPremium: number | null
  groupStatus: QuoteDisplayStatus
  latestDate: string | null
}

export function QuoteTracking({ projectId, coverages }: QuoteTrackingProps) {
  const { data: quotes, isLoading } = useBrokerQuotes(projectId)
  const followupsMutation = useDraftFollowups(projectId)
  const [expandedCarrier, setExpandedCarrier] = useState<string | null>(null)
  const [showManualFor, setShowManualFor] = useState<string | null>(null)

  // Build coverage lookup map from coverage_id -> ProjectCoverage
  const coverageMap = useMemo(() => {
    const map = new Map<string, ProjectCoverage>()
    for (const c of coverages) {
      map.set(c.id, c)
    }
    return map
  }, [coverages])

  // Group quotes by carrier
  const carrierGroups = useMemo<CarrierGroup[]>(() => {
    if (!quotes) return []
    const map = new Map<string, CarrierQuote[]>()
    for (const q of quotes) {
      const key = q.carrier_config_id || q.carrier_name
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(q)
    }
    return Array.from(map.entries()).map(([key, groupQuotes]) => {
      const first = groupQuotes[0]
      const premiums = groupQuotes.filter(q => q.premium != null).map(q => q.premium!)
      const totalPremium = premiums.length > 0 ? premiums.reduce((a, b) => a + b, 0) : null

      // Find the latest date (received or solicited)
      const dates = groupQuotes
        .map(q => q.received_at || q.solicited_at)
        .filter(Boolean) as string[]
      const latestDate = dates.length > 0
        ? dates.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0]
        : null

      return {
        key,
        carrierName: first.carrier_name,
        carrierType: first.carrier_type,
        quotes: groupQuotes,
        totalPremium,
        groupStatus: getGroupStatus(groupQuotes),
        latestDate,
      }
    })
  }, [quotes])

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

  // Count unique carriers by status
  const receivedCarriers = carrierGroups.filter(g =>
    ['received', 'extracting', 'extracted', 'selected'].includes(g.groupStatus)
  ).length
  const pendingCarriers = carrierGroups.filter(g =>
    ['solicited', 'pending', 'needs_follow_up'].includes(g.groupStatus)
  ).length
  const hasReceived = quotes.some(q => ['received', 'selected'].includes(q.status))
  const allExtracted = quotes.length > 0 && quotes.every(q => ['extracted', 'received', 'selected'].includes(q.status))
  const hasSolicited = quotes.some((q) => q.status === 'solicited')

  return (
    <div className="space-y-4">
      {/* Header with summary badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="text-lg font-medium">Quote Tracking</h3>
        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-700 px-2.5 py-0.5 text-xs font-medium">
          {receivedCarriers} of {carrierGroups.length} carriers received
        </span>
        {pendingCarriers > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 text-orange-700 px-2.5 py-0.5 text-xs font-medium">
            <span className="animate-pulse inline-block w-1.5 h-1.5 rounded-full bg-orange-500" />
            {pendingCarriers} pending
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
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Total Premium</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Latest Activity</th>
            </tr>
          </thead>
          <tbody>
            {carrierGroups.map((group) => {
              const isExpanded = expandedCarrier === group.key

              return (
                <>
                  {/* Carrier summary row */}
                  <tr
                    key={group.key}
                    className={`border-t hover:bg-muted/20 transition-colors cursor-pointer ${isExpanded ? 'bg-muted/10' : ''}`}
                    onClick={() => setExpandedCarrier(k => k === group.key ? null : group.key)}
                  >
                    {/* Carrier with logo */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <CarrierBadge name={group.carrierName} className="font-medium text-sm" />
                        {group.quotes.length > 1 && (
                          <span className="text-xs text-muted-foreground bg-muted rounded-full px-1.5 py-0.5">
                            {group.quotes.length} lines
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Type badge */}
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        group.carrierType === 'insurance'
                          ? 'bg-[rgba(233,77,53,0.1)] text-[#E94D35]'
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {group.carrierType === 'insurance' ? 'Insurance' : 'Surety'}
                      </span>
                    </td>

                    {/* Status badge */}
                    <td className="px-4 py-3">
                      <Badge className={`text-xs ${statusBadgeVariant(group.groupStatus)}`}>
                        {group.groupStatus === 'extracting' && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                        {statusLabel(group.groupStatus)}
                      </Badge>
                    </td>

                    {/* Total Premium */}
                    <td className="px-4 py-3">
                      {group.totalPremium != null ? (
                        <span className="text-sm font-bold">{formatCurrency(group.totalPremium)}</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">---</span>
                      )}
                    </td>

                    {/* Latest activity */}
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <span>
                          {group.latestDate
                            ? format(new Date(group.latestDate), 'MMM d')
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

                  {/* Expanded: individual quote line items */}
                  {isExpanded && group.quotes.map((quote) => (
                    <QuoteLineItem
                      key={quote.id}
                      quote={quote}
                      projectId={projectId}
                      showManualFor={showManualFor}
                      setShowManualFor={setShowManualFor}
                      coverageMap={coverageMap}
                    />
                  ))}
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
