import { useState, useEffect } from 'react'
import type { KnowledgeHealth } from '@/types/streams'

interface KnowledgeHealthBarProps {
  health: KnowledgeHealth
}

export function KnowledgeHealthBar({ health }: KnowledgeHealthBarProps) {
  const percentage = Math.min(Math.max(health.avg_density, 0), 100)
  const [animatedWidth, setAnimatedWidth] = useState(0)

  useEffect(() => {
    // Delay slightly so the transition is visible after mount
    const timer = setTimeout(() => setAnimatedWidth(percentage), 50)
    return () => clearTimeout(timer)
  }, [percentage])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span
          className="text-sm font-medium"
          style={{ color: 'var(--heading-text)' }}
        >
          Intelligence Health
        </span>
        <span
          className="text-sm font-semibold"
          style={{ color: 'var(--brand-coral)' }}
        >
          {Math.round(percentage)}%
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: 'var(--brand-light)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${animatedWidth}%`,
            background: 'linear-gradient(to right, var(--brand-coral), var(--brand-gradient-end))',
          }}
        />
      </div>
      <p className="text-sm" style={{ color: 'var(--secondary-text)' }}>
        {health.total_entries} entr{health.total_entries === 1 ? 'y' : 'ies'} &middot;{' '}
        {health.stream_count} focus area{health.stream_count === 1 ? '' : 's'}
      </p>
    </div>
  )
}
