import { TrendingUp, TrendingDown } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  icon?: React.ReactNode
  trend?: { value: number; label: string }
}

export function MetricCard({ label, value, sub, accent, icon, trend }: MetricCardProps) {
  const isPositiveTrend = trend && trend.value >= 0
  const isNegativeTrend = trend && trend.value < 0

  return (
    <div
      className="relative overflow-hidden bg-white rounded-xl shadow-sm border p-4 flex flex-col gap-1 transition-shadow hover:shadow-md"
      style={accent ? { borderLeft: '3px solid #E94D35' } : undefined}
    >
      {/* Subtle background tint */}
      {accent && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'rgba(233, 77, 53, 0.03)' }}
        />
      )}

      {/* Top row: label + icon */}
      <div className="flex items-center justify-between relative">
        <span className="text-sm text-muted-foreground">{label}</span>
        {icon && (
          <span className="text-muted-foreground/40">{icon}</span>
        )}
      </div>

      {/* Value */}
      <span className="text-2xl font-semibold text-foreground relative">{value}</span>

      {/* Bottom row: sub text + trend */}
      <div className="flex items-center justify-between relative">
        {sub ? (
          <span className="text-xs text-muted-foreground">{sub}</span>
        ) : (
          <span />
        )}
        {trend && (
          <span
            className={`inline-flex items-center gap-0.5 text-xs font-medium ${
              isPositiveTrend ? 'text-emerald-600' : 'text-red-500'
            }`}
          >
            {isPositiveTrend ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {isPositiveTrend ? '+' : ''}{trend.value}%
            <span className="text-muted-foreground font-normal ml-0.5">{trend.label}</span>
          </span>
        )}
      </div>
    </div>
  )
}
