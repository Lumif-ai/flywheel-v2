import { useCallback } from 'react'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { STAGE_COLORS, STAGE_ORDER } from '../types/lead'

interface LeadsFunnelProps {
  funnel: Record<string, number>
  total: number
  activeStage: string | null
  onStageChange: (stage: string | null) => void
  isLoading: boolean
}

export function LeadsFunnel({ funnel, activeStage, onStageChange, isLoading }: LeadsFunnelProps) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      let nextIndex = -1
      if (e.key === 'ArrowRight') {
        nextIndex = (index + 1) % STAGE_ORDER.length
      } else if (e.key === 'ArrowLeft') {
        nextIndex = (index - 1 + STAGE_ORDER.length) % STAGE_ORDER.length
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        const stage = STAGE_ORDER[index]
        onStageChange(activeStage === stage ? null : stage)
        return
      } else {
        return
      }
      e.preventDefault()
      const container = e.currentTarget.parentElement
      if (container) {
        const tabs = container.querySelectorAll('[role="tab"]')
        ;(tabs[nextIndex] as HTMLElement)?.focus()
      }
    },
    [activeStage, onStageChange]
  )

  if (isLoading) {
    return (
      <ShimmerSkeleton
        style={{ width: '100%', height: '64px', borderRadius: '12px' }}
      />
    )
  }

  const allZero = STAGE_ORDER.every((s) => (funnel[s] ?? 0) === 0)

  return (
    <div
      role="tablist"
      aria-label="Pipeline funnel"
      style={{
        display: 'flex',
        width: '100%',
        height: '64px',
        borderRadius: '12px',
        overflow: 'hidden',
        gap: '2px',
        opacity: allZero ? 0.5 : 1,
      }}
    >
      {STAGE_ORDER.map((stage, i) => {
        const count = funnel[stage] ?? 0
        const color = STAGE_COLORS[stage] ?? '#6b7280'
        const isActive = activeStage === stage
        const isFirst = i === 0
        const isLast = i === STAGE_ORDER.length - 1

        return (
          <button
            key={stage}
            role="tab"
            aria-selected={isActive}
            aria-label={`Filter by ${stage}: ${count} leads`}
            tabIndex={isActive || (activeStage === null && i === 0) ? 0 : -1}
            onClick={() => onStageChange(isActive ? null : stage)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            style={{
              flex: `${Math.max(count, 1)}`,
              minWidth: '56px',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '2px',
              background: `${color}1f`,
              border: 'none',
              borderBottom: isActive ? `2px solid ${color}` : '2px solid transparent',
              borderRadius: isFirst ? '12px 0 0 12px' : isLast ? '0 12px 12px 0' : '0',
              cursor: 'pointer',
              transition: 'filter 200ms ease, border-color 200ms ease',
              padding: 0,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.filter = 'brightness(1.08)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.filter = 'brightness(1)'
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color,
                lineHeight: 1,
              }}
            >
              {stage}
            </span>
            <span
              style={{
                fontSize: '18px',
                fontWeight: isActive ? 800 : 700,
                color,
                fontVariantNumeric: 'tabular-nums',
                lineHeight: 1,
              }}
            >
              {count}
            </span>
          </button>
        )
      })}
    </div>
  )
}
