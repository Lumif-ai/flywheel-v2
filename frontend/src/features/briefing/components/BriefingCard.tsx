import { useState } from 'react'
import { Link } from 'react-router'
import {
  CalendarIcon,
  LightbulbIcon,
  AlertTriangleIcon,
  XIcon,
  BrainIcon,
  ClockIcon,
  LinkIcon,
  ChevronDownIcon,
} from 'lucide-react'
import type { BriefingCard as BriefingCardType } from '@/types/streams'
import { useDismissCard } from '../hooks/useBriefing'

const iconMap = {
  meeting: CalendarIcon,
  suggestion: LightbulbIcon,
  stale: AlertTriangleIcon,
} as const

const attributionIconMap: Record<string, typeof CalendarIcon> = {
  calendar: CalendarIcon,
  learning_engine: BrainIcon,
  staleness_check: ClockIcon,
  entity_match: LinkIcon,
}

function formatRelativeTime(isoString: string): string {
  const diff = new Date(isoString).getTime() - Date.now()
  const hours = Math.round(diff / (1000 * 60 * 60))
  if (hours > 0) return `in ${hours} hour${hours === 1 ? '' : 's'}`
  if (hours === 0) return 'soon'
  return `${Math.abs(hours)} hour${Math.abs(hours) === 1 ? '' : 's'} ago`
}

function getSuggestionKey(card: BriefingCardType): string {
  if (card.suggestion_key) return card.suggestion_key
  if (card.card_type === 'meeting' && card.metadata.work_item_id) {
    return String(card.metadata.work_item_id)
  }
  if (card.card_type === 'stale' && card.metadata.file_name) {
    return `stale:${card.metadata.file_name}`
  }
  return ''
}

interface BriefingCardProps {
  card: BriefingCardType
}

export function BriefingCard({ card }: BriefingCardProps) {
  const [showAttribution, setShowAttribution] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const dismissMutation = useDismissCard()

  const Icon = iconMap[card.card_type]
  const isStale = card.card_type === 'stale'
  const scheduledTime =
    card.card_type === 'meeting' && card.metadata.scheduled_time
      ? String(card.metadata.scheduled_time)
      : null

  const handleDismiss = () => {
    setDismissed(true)
    dismissMutation.mutate({
      card_type: card.card_type,
      suggestion_key: getSuggestionKey(card),
    })
  }

  if (dismissed) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-center text-sm text-muted-foreground opacity-60 transition-opacity duration-300">
        Dismissed
      </div>
    )
  }

  return (
    <div
      className={`group relative rounded-xl border p-4 ${
        isStale
          ? 'border-yellow-200 bg-yellow-50/50'
          : 'border-border bg-card'
      }`}
    >
      {/* Dismiss button -- visible on hover */}
      <button
        onClick={handleDismiss}
        className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
        title="Dismiss card"
      >
        <XIcon className="h-3.5 w-3.5" />
      </button>

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

          {/* Reason footer */}
          {card.reason && (
            <div className="mt-3 border-t border-border/50 pt-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground/70">
                  {card.reason}
                </span>
                {card.source_attribution && card.source_attribution.length > 0 && (
                  <button
                    onClick={() => setShowAttribution(!showAttribution)}
                    className="inline-flex items-center gap-0.5 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                  >
                    Why?
                    <ChevronDownIcon
                      className={`h-3 w-3 transition-transform ${
                        showAttribution ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                )}
              </div>

              {/* Expandable source attribution */}
              {showAttribution && card.source_attribution && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {card.source_attribution.map((attr, i) => {
                    const AttrIcon = attributionIconMap[attr.type] || LinkIcon
                    return (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded-full bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
                      >
                        <AttrIcon className="h-3 w-3" />
                        {attr.name}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
