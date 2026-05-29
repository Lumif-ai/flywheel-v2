import type { ProjectCoverage } from '../types/broker'

interface RequirementCardProps {
  coverage: ProjectCoverage
  style?: React.CSSProperties
  isActive?: boolean
  onClauseClick?: (coverage: ProjectCoverage) => void
}

const SOURCE_STYLE: Record<string, string> = {
  ai: 'bg-violet-100 text-violet-700',
  ai_extraction: 'bg-violet-100 text-violet-700',
  manual: 'bg-blue-100 text-blue-700',
  contract: 'bg-amber-100 text-amber-700',
}

const CATEGORY_STYLE: Record<string, string> = {
  insurance: 'bg-[rgba(233,77,53,0.1)] text-[#E94D35]',
  surety: 'bg-blue-100 text-blue-700',
}

export function RequirementCard({
  coverage,
  style,
  isActive = false,
  onClauseClick,
}: RequirementCardProps) {
  const formattedLimit =
    coverage.required_limit != null
      ? new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: coverage.limit_currency || 'USD',
          maximumFractionDigits: 0,
        }).format(coverage.required_limit)
      : null

  // NAV-06: active state renders a 4px coral left border. We must explicitly re-add
  // the 1px top/right/bottom borders when active because `border-l-4` overrides
  // ONLY the left edge (other edges would otherwise revert to 0).
  const borderClass = isActive
    ? 'border-l-4 border-l-[#E94D35] border-y border-r border-border'
    : 'border border-border'

  return (
    <div
      className={`rounded-xl p-4 space-y-3 animate-fade-slide-up bg-card hover:shadow-sm transition-shadow ${borderClass}`}
      style={style}
    >
      {/* Header: coverage name + required limit */}
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground leading-snug">
          {coverage.display_name ?? coverage.coverage_type}
        </h4>
        {formattedLimit ? (
          <span className="text-sm font-bold text-foreground flex-shrink-0">
            {formattedLimit}
          </span>
        ) : (
          <span className="text-xs px-2.5 py-0.5 rounded-full font-medium flex-shrink-0 bg-muted text-muted-foreground">
            No limit specified
          </span>
        )}
      </div>

      {/* Description — supporting detail text */}
      {coverage.required_terms && coverage.required_terms !== coverage.display_name && (
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
          {coverage.required_terms}
        </p>
      )}

      {/* Badges row: source + category + critical */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {coverage.source && (
          <span className={`text-xs px-2 py-0.5 rounded-full capitalize font-medium ${SOURCE_STYLE[coverage.source] ?? 'bg-muted text-muted-foreground'}`}>
            {coverage.source.replace(/_/g, ' ')}
          </span>
        )}
        <span className={`text-xs px-2 py-0.5 rounded-full capitalize font-medium ${CATEGORY_STYLE[coverage.category] ?? 'bg-muted text-muted-foreground'}`}>
          {coverage.category}
        </span>
        {coverage.ai_critical_finding && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold">
            Critical Finding
          </span>
        )}
      </div>

      {/* Contract clause — clickable coral link */}
      {coverage.contract_clause && (
        <button
          type="button"
          className="w-full text-left text-xs text-[#E94D35] hover:text-[#d4432e] font-medium border-t pt-2.5 leading-relaxed cursor-pointer transition-colors flex items-center gap-1"
          onClick={() => onClauseClick?.(coverage)}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span className="line-clamp-2">{coverage.contract_clause}</span>
        </button>
      )}
    </div>
  )
}
