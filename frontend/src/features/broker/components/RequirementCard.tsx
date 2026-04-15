import type { ProjectCoverage } from '../types/broker'

interface RequirementCardProps {
  coverage: ProjectCoverage
  style?: React.CSSProperties
}

const CONFIDENCE_PCT: Record<string, number> = {
  high: 90,
  medium: 60,
  low: 30,
}

const GAP_STATUS_STYLE: Record<string, string> = {
  covered: 'bg-green-100 text-green-700',
  insufficient: 'bg-amber-100 text-amber-700',
  missing: 'bg-red-100 text-red-700',
  unknown: 'bg-muted text-muted-foreground',
}

export function RequirementCard({ coverage, style }: RequirementCardProps) {
  const confidencePct = CONFIDENCE_PCT[coverage.confidence?.toLowerCase()] ?? 60
  const gapStyle = GAP_STATUS_STYLE[coverage.gap_status] ?? GAP_STATUS_STYLE.unknown

  const formattedLimit =
    coverage.required_limit != null
      ? new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          maximumFractionDigits: 0,
        }).format(coverage.required_limit)
      : null

  return (
    <div
      className="rounded-xl border p-4 space-y-3 animate-fade-slide-up bg-card"
      style={style}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-semibold truncate">
            {coverage.display_name ?? coverage.coverage_type}
          </p>
          <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground capitalize">
            {coverage.category}
          </span>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {coverage.ai_critical_finding && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
              Critical
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full capitalize font-medium ${gapStyle}`}>
            {coverage.gap_status}
          </span>
        </div>
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground">Confidence</span>
          <span className="text-xs text-muted-foreground capitalize">{coverage.confidence}</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-[#E94D35] transition-all"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      {/* Required limit */}
      {formattedLimit && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Required Limit</span>
          <span className="font-medium">{formattedLimit}</span>
        </div>
      )}

      {/* Contract clause */}
      {coverage.contract_clause && (
        <p className="text-xs text-muted-foreground border-t pt-2 leading-relaxed line-clamp-2">
          {coverage.contract_clause}
        </p>
      )}
    </div>
  )
}
