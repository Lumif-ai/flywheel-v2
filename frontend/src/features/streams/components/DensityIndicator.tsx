import { cn } from '@/lib/cn'
import type { DensityDetails } from '@/types/streams'

function getDensityColor(score: number): string {
  if (score >= 70) return 'bg-green-500'
  if (score >= 30) return 'bg-yellow-500'
  return 'bg-blue-500'
}

function getDensityTextColor(score: number): string {
  if (score >= 70) return 'text-green-600'
  if (score >= 30) return 'text-yellow-600'
  return 'text-blue-600'
}

interface DensityDotProps {
  score: number
  className?: string
}

export function DensityDot({ score, className }: DensityDotProps) {
  return (
    <span
      className={cn(
        'inline-block h-2 w-2 rounded-full shrink-0',
        getDensityColor(score),
        className
      )}
      title={`${score}% coverage`}
    />
  )
}

interface DensityBarProps {
  score: number
  showLabel?: boolean
  className?: string
}

export function DensityBar({ score, showLabel, className }: DensityBarProps) {
  const clamped = Math.max(0, Math.min(100, score))

  return (
    <div className={className}>
      <div className="h-2 w-full rounded-full bg-muted">
        <div
          className={cn('h-2 rounded-full transition-all', getDensityColor(clamped))}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <p className="mt-1 text-xs text-muted-foreground">{clamped}% coverage</p>
      )}
    </div>
  )
}

interface StreamDensityCardProps {
  densityScore: number
  details: DensityDetails | null
  compact?: boolean
}

export function StreamDensityCard({ densityScore, details, compact }: StreamDensityCardProps) {
  const clamped = Math.max(0, Math.min(100, densityScore))

  if (compact) {
    return (
      <div className="flex items-center gap-1.5 shrink-0">
        <div className="h-1.5 w-16 rounded-full bg-muted">
          <div
            className={cn('h-1.5 rounded-full transition-all', getDensityColor(clamped))}
            style={{ width: `${clamped}%` }}
          />
        </div>
        <span className={cn('text-[10px] font-medium tabular-nums', getDensityTextColor(clamped))}>
          {clamped}%
        </span>
      </div>
    )
  }

  const strong = details?.strong_dimensions ?? []
  const gaps = details?.gap_dimensions ?? []
  const hasStrong = strong.length > 0
  const hasGaps = gaps.length > 0

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <DensityBar score={clamped} className="flex-1" />
        <span className={cn('text-sm font-medium tabular-nums', getDensityTextColor(clamped))}>
          {clamped}%
        </span>
      </div>

      {details && (
        <>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <span>{details.entry_count} entries</span>
            <span className="text-muted-foreground/50">&middot;</span>
            <span>{details.meeting_count} meetings</span>
            <span className="text-muted-foreground/50">&middot;</span>
            <span>{details.people_count} people</span>
          </div>

          {(hasStrong || hasGaps) && (
            <p className="text-xs text-muted-foreground">
              {hasStrong && <span>Strong: {strong.join(', ')}</span>}
              {hasStrong && hasGaps && <span>. </span>}
              {hasGaps && <span>Gaps: {gaps.join(', ')}</span>}
            </p>
          )}
        </>
      )}
    </div>
  )
}
