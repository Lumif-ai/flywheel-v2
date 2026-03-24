import { Link } from 'react-router'
import { TrendingUp, DollarSign, Eye } from 'lucide-react'
import { typography, colors } from '@/lib/design-tokens'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NextActionCtaProps {
  primaryPriority: string // "grow_revenue" | "raise_capital" | "track_competitors"
}

interface CtaConfig {
  title: string
  description: string
  action: string
  href: string
  Icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
}

// ---------------------------------------------------------------------------
// Priority CTA map
// ---------------------------------------------------------------------------

const PRIORITY_CTAS: Record<string, CtaConfig> = {
  grow_revenue: {
    title: 'Research your first prospect',
    description:
      "Paste a prospect's website to get an instant account brief with competitive angles, stakeholder map, and talking points.",
    action: 'Start research',
    href: '/chat',
    Icon: TrendingUp,
  },
  raise_capital: {
    title: 'Prep for your next investor meeting',
    description:
      "Share who you're meeting with and we'll build a briefing with their portfolio, thesis, and the questions they'll ask.",
    action: 'Prep a meeting',
    href: '/chat',
    Icon: DollarSign,
  },
  track_competitors: {
    title: 'Add a competitor to watch',
    description:
      "Paste a competitor's website to build a competitive profile — pricing, positioning, customers, and where you win.",
    action: 'Add competitor',
    href: '/chat',
    Icon: Eye,
  },
}

const DEFAULT_PRIORITY = 'grow_revenue'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NextActionCta({ primaryPriority }: NextActionCtaProps) {
  const cta = PRIORITY_CTAS[primaryPriority] ?? PRIORITY_CTAS[DEFAULT_PRIORITY]
  const { title, description, action, href, Icon } = cta

  return (
    <div
      style={{
        maxWidth: '640px',
        margin: '0 auto',
        borderRadius: '12px',
        border: `1px solid ${colors.subtleBorder}`,
        background: '#ffffff',
        display: 'flex',
        overflow: 'hidden',
      }}
    >
      {/* Left accent bar */}
      <div
        style={{
          width: '3px',
          background: colors.brandCoral,
          flexShrink: 0,
        }}
      />

      {/* Content */}
      <div style={{ padding: '20px 24px', flex: 1 }}>
        {/* Icon + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <Icon
            style={{
              width: '18px',
              height: '18px',
              color: colors.brandCoral,
              flexShrink: 0,
            }}
          />
          <h3
            style={{
              fontSize: typography.body.size,
              fontWeight: '600',
              color: colors.headingText,
              margin: 0,
            }}
          >
            {title}
          </h3>
        </div>

        {/* Description */}
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
            margin: '0 0 16px',
            lineHeight: '1.5',
          }}
        >
          {description}
        </p>

        {/* CTA row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link
            to={href}
            className="no-underline"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '8px 20px',
              borderRadius: '999px',
              background: colors.brandCoral,
              color: '#ffffff',
              fontSize: typography.body.size,
              fontWeight: '500',
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.opacity = '0.85')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.opacity = '1')}
          >
            {action}
          </Link>
          <Link
            to="/"
            className="no-underline hover:underline"
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
            }}
          >
            or explore your workspace &rarr;
          </Link>
        </div>
      </div>
    </div>
  )
}
