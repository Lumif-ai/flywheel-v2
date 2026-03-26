import { useNavigate } from 'react-router'
import { Mail, AlertCircle, ArrowUp, TrendingUp } from 'lucide-react'
import { usePulse } from '../hooks/usePulse'
import { BrandedCard } from '@/components/ui/branded-card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors } from '@/lib/design-tokens'
import type { PulseSignal } from '../types/pulse'

type CardVariant = 'complete' | 'warning' | 'action'

const SIGNAL_CONFIG: Record<
  PulseSignal['type'],
  { icon: typeof Mail; iconColor: string; variant: CardVariant }
> = {
  reply_received: { icon: Mail, iconColor: colors.success, variant: 'complete' },
  followup_overdue: { icon: AlertCircle, iconColor: colors.warning, variant: 'warning' },
  bump_suggested: { icon: ArrowUp, iconColor: '#3b82f6', variant: 'action' },
}

function formatTimeAgo(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function SignalCard({ signal }: { signal: PulseSignal }) {
  const navigate = useNavigate()
  const config = SIGNAL_CONFIG[signal.type]
  const Icon = config.icon

  return (
    <BrandedCard
      variant={config.variant}
      onClick={() => navigate(`/accounts/${signal.account_id}`)}
    >
      <div className="flex items-start gap-3">
        <div
          className="shrink-0 mt-0.5"
          style={{ color: config.iconColor }}
        >
          <Icon className="size-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p
            style={{
              fontSize: typography.body.size,
              fontWeight: '500',
              color: colors.headingText,
              margin: 0,
              lineHeight: '1.3',
            }}
          >
            {signal.title}
          </p>
          <p
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
              margin: '4px 0 0 0',
              lineHeight: typography.caption.lineHeight,
            }}
          >
            {signal.detail}
          </p>
          <div
            className="flex items-center gap-2 mt-2"
          >
            <Badge variant="secondary" className="text-[11px]">
              {signal.account_name}
            </Badge>
            <span
              style={{
                fontSize: '11px',
                color: colors.secondaryText,
              }}
            >
              {formatTimeAgo(signal.created_at)}
            </span>
          </div>
        </div>
      </div>
    </BrandedCard>
  )
}

export function PulseSignals() {
  const { data, isLoading } = usePulse(5)

  const signals = data?.items ?? []

  return (
    <div>
      <div className="flex items-center gap-2" style={{ marginBottom: '12px' }}>
        <TrendingUp className="size-4" style={{ color: colors.brandCoral }} />
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
          }}
        >
          Revenue Signals
        </h2>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : signals.length === 0 ? (
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          No signals right now
        </p>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  )
}
