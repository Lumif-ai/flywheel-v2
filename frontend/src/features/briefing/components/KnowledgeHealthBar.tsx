import type { KnowledgeHealth } from '@/types/streams'

function getBarColor(level: KnowledgeHealth['level']): string {
  switch (level) {
    case 'strong':
      return 'bg-green-500'
    case 'growing':
      return 'bg-yellow-500'
    case 'early':
      return 'bg-blue-500'
  }
}

interface KnowledgeHealthBarProps {
  health: KnowledgeHealth
}

export function KnowledgeHealthBar({ health }: KnowledgeHealthBarProps) {
  const percentage = Math.min(Math.max(health.avg_density, 0), 100)
  const barColor = getBarColor(health.level)

  return (
    <div className="space-y-1.5">
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-sm text-muted-foreground">
        {health.stream_count} stream{health.stream_count === 1 ? '' : 's'} |{' '}
        {health.total_entries} entr{health.total_entries === 1 ? 'y' : 'ies'} |{' '}
        {health.level}
      </p>
    </div>
  )
}
