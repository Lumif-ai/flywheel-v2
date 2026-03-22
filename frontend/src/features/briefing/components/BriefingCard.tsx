import { Link } from 'react-router'
import { CalendarIcon, LightbulbIcon, AlertTriangleIcon } from 'lucide-react'
import type { BriefingCard as BriefingCardType } from '@/types/streams'

const iconMap = {
  meeting: CalendarIcon,
  suggestion: LightbulbIcon,
  stale: AlertTriangleIcon,
} as const

function formatRelativeTime(isoString: string): string {
  const diff = new Date(isoString).getTime() - Date.now()
  const hours = Math.round(diff / (1000 * 60 * 60))
  if (hours > 0) return `in ${hours} hour${hours === 1 ? '' : 's'}`
  if (hours === 0) return 'soon'
  return `${Math.abs(hours)} hour${Math.abs(hours) === 1 ? '' : 's'} ago`
}

interface BriefingCardProps {
  card: BriefingCardType
}

export function BriefingCard({ card }: BriefingCardProps) {
  const Icon = iconMap[card.card_type]
  const isStale = card.card_type === 'stale'
  const scheduledTime =
    card.card_type === 'meeting' && card.metadata.scheduled_time
      ? String(card.metadata.scheduled_time)
      : null

  return (
    <div
      className={`rounded-xl border p-4 ${
        isStale
          ? 'border-yellow-200 bg-yellow-50/50'
          : 'border-border bg-card'
      }`}
    >
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium leading-tight">{card.title}</h3>
            {scheduledTime && (
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatRelativeTime(scheduledTime)}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{card.body}</p>
          {card.entity_name && (
            <div className="mt-2">
              {card.stream_id ? (
                <Link
                  to={`/streams/${card.stream_id}`}
                  className="text-sm text-primary hover:underline"
                >
                  {card.entity_name}
                </Link>
              ) : (
                <span className="text-sm text-muted-foreground">
                  {card.entity_name}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
