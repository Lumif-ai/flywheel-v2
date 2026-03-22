import { cn } from '@/lib/cn'

function getDensityColor(score: number): string {
  if (score >= 70) return 'bg-green-500'
  if (score >= 30) return 'bg-yellow-500'
  return 'bg-blue-500'
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
}

export function DensityBar({ score, showLabel }: DensityBarProps) {
  const clamped = Math.max(0, Math.min(100, score))

  return (
    <div>
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
