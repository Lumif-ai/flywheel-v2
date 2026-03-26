import { useState } from 'react'
import { Link } from 'react-router'
import { Loader2 } from 'lucide-react'
import { usePipeline } from '../hooks/usePipeline'
import { useGraduate } from '../hooks/useGraduate'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { spacing, typography, colors } from '@/lib/design-tokens'
import type { PipelineItem } from '../types/pipeline'

const PAGE_SIZE = 20

const FIT_TIER_COLORS: Record<string, { bg: string; text: string }> = {
  excellent: { bg: 'rgba(34,197,94,0.12)', text: '#16a34a' },
  good: { bg: 'rgba(59,130,246,0.12)', text: '#2563eb' },
  fair: { bg: 'rgba(245,158,11,0.12)', text: '#d97706' },
  poor: { bg: 'rgba(239,68,68,0.12)', text: '#dc2626' },
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function DaysSinceCell({ days }: { days: number | null }) {
  if (days == null) {
    return (
      <span style={{ color: colors.secondaryText }}>
        &mdash;
      </span>
    )
  }
  let color: string = colors.success
  if (days >= 7 && days <= 14) color = colors.warning
  if (days > 14) color = colors.error
  return <span style={{ color, fontWeight: '500' }}>{days}</span>
}

function FitScoreBadge({ tier, score }: { tier: string | null; score: number | null }) {
  if (!tier) {
    return (
      <span style={{ color: colors.secondaryText, fontSize: typography.caption.size }}>
        &mdash;
      </span>
    )
  }
  const tierLower = tier.toLowerCase()
  const palette = FIT_TIER_COLORS[tierLower] ?? FIT_TIER_COLORS.fair
  return (
    <Badge
      className="gap-1"
      style={{
        backgroundColor: palette.bg,
        color: palette.text,
        border: 'none',
      }}
    >
      {tier}
      {score != null && (
        <span style={{ opacity: 0.7, fontSize: '10px' }}>
          {score}
        </span>
      )}
    </Badge>
  )
}

function OutreachStatusBadge({ status, count }: { status: string | null; count: number }) {
  if (!status) {
    return (
      <span style={{ color: colors.secondaryText, fontSize: typography.caption.size }}>
        None
      </span>
    )
  }
  return (
    <Badge variant="outline" className="gap-1">
      {status}
      {count > 0 && (
        <span style={{ opacity: 0.6 }}>({count})</span>
      )}
    </Badge>
  )
}

function GraduateButton({ accountId }: { accountId: string }) {
  const graduate = useGraduate()

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={graduate.isPending}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        graduate.mutate(accountId)
      }}
    >
      {graduate.isPending ? (
        <Loader2 className="size-3 animate-spin" />
      ) : (
        'Graduate'
      )}
    </Button>
  )
}

export function PipelinePage() {
  const [offset, setOffset] = useState(0)
  const [fitTier, setFitTier] = useState<string | undefined>(undefined)
  const [outreachStatus, setOutreachStatus] = useState<string | undefined>(undefined)

  const { data, isLoading } = usePipeline({
    offset,
    limit: PAGE_SIZE,
    fit_tier: fitTier,
    outreach_status: outreachStatus,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const selectStyle: React.CSSProperties = {
    fontSize: typography.caption.size,
    padding: '6px 10px',
    borderRadius: '8px',
    border: `1px solid ${colors.subtleBorder}`,
    background: colors.cardBg,
    color: colors.headingText,
    cursor: 'pointer',
  }

  return (
    <div
      className="page-enter"
      style={{ padding: spacing.pageDesktop, background: colors.pageBg }}
    >
      <div className="mx-auto" style={{ maxWidth: spacing.maxGrid }}>
        {/* Header */}
        <div style={{ marginBottom: spacing.section }}>
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
              color: colors.headingText,
              marginBottom: '4px',
            }}
          >
            Pipeline
          </h1>
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
            Prospect accounts ready for outreach
          </p>
        </div>

        {/* Filters */}
        <div
          className="flex items-center gap-3 flex-wrap"
          style={{ marginBottom: spacing.element }}
        >
          <select
            value={fitTier ?? ''}
            onChange={(e) => {
              setFitTier(e.target.value || undefined)
              setOffset(0)
            }}
            style={selectStyle}
          >
            <option value="">All Tiers</option>
            <option value="Excellent">Excellent</option>
            <option value="Good">Good</option>
            <option value="Fair">Fair</option>
            <option value="Poor">Poor</option>
          </select>
          <select
            value={outreachStatus ?? ''}
            onChange={(e) => {
              setOutreachStatus(e.target.value || undefined)
              setOffset(0)
            }}
            style={selectStyle}
          >
            <option value="">All Statuses</option>
            <option value="sent">Sent</option>
            <option value="opened">Opened</option>
            <option value="replied">Replied</option>
            <option value="bounced">Bounced</option>
          </select>
        </div>

        {/* Table */}
        <div
          style={{
            background: colors.cardBg,
            borderRadius: '12px',
            border: `1px solid ${colors.subtleBorder}`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
            overflow: 'hidden',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr
                style={{
                  borderBottom: `1px solid ${colors.subtleBorder}`,
                  textAlign: 'left',
                }}
              >
                {['Company', 'Fit Score', 'Outreach Status', 'Last Outreach', 'Days Since Action', 'Actions'].map(
                  (header) => (
                    <th
                      key={header}
                      style={{
                        padding: '12px 16px',
                        fontSize: typography.caption.size,
                        fontWeight: '500',
                        color: colors.secondaryText,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {header}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${colors.subtleBorder}` }}>
                    {Array.from({ length: 6 }).map((__, j) => (
                      <td key={j} style={{ padding: '12px 16px' }}>
                        <Skeleton className="h-5 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      padding: '48px 16px',
                      textAlign: 'center',
                      color: colors.secondaryText,
                      fontSize: typography.body.size,
                    }}
                  >
                    No prospects in pipeline
                  </td>
                </tr>
              ) : (
                items.map((item: PipelineItem) => (
                  <tr
                    key={item.id}
                    style={{ borderBottom: `1px solid ${colors.subtleBorder}` }}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td style={{ padding: '12px 16px' }}>
                      <Link
                        to={`/accounts/${item.id}`}
                        className="no-underline hover:underline"
                        style={{
                          fontWeight: '500',
                          color: colors.headingText,
                          fontSize: typography.body.size,
                        }}
                      >
                        {item.name}
                      </Link>
                      {item.domain && (
                        <div
                          style={{
                            fontSize: typography.caption.size,
                            color: colors.secondaryText,
                          }}
                        >
                          {item.domain}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <FitScoreBadge tier={item.fit_tier} score={item.fit_score} />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <OutreachStatusBadge
                        status={item.last_outreach_status}
                        count={item.outreach_count}
                      />
                    </td>
                    <td
                      style={{
                        padding: '12px 16px',
                        fontSize: typography.caption.size,
                        color: colors.secondaryText,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatRelativeTime(item.last_interaction_at)}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <DaysSinceCell days={item.days_since_last_outreach} />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <GraduateButton accountId={item.id} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 0 && (
          <div
            className="flex items-center justify-between"
            style={{ marginTop: spacing.element }}
          >
            <span
              style={{
                fontSize: typography.caption.size,
                color: colors.secondaryText,
              }}
            >
              {offset + 1}&ndash;{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <span
                style={{
                  fontSize: typography.caption.size,
                  color: colors.secondaryText,
                }}
              >
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
