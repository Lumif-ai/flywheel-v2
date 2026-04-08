import { NavLink } from 'react-router'
import { Calendar, Zap, MessageSquare } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { spacing, typography, colors } from '@/lib/design-tokens'

const actions = [
  {
    icon: Calendar,
    title: 'Connect your calendar',
    subtitle: 'See today\'s meetings and get prep briefings',
    to: '/settings',
    state: undefined,
  },
  {
    icon: Zap,
    title: 'Run meeting processor',
    subtitle: 'Analyze past meetings for insights',
    to: '/chat',
    state: { prefill: 'Run meeting-processor' },
  },
  {
    icon: MessageSquare,
    title: 'Ask your team in chat',
    subtitle: 'Get answers from your AI team',
    to: '/chat',
    state: undefined,
  },
] as const

export function ColdStartCard() {
  return (
    <BrandedCard hoverable={false} className="!bg-[var(--brand-tint-warm)]">
      <h2
        style={{
          fontSize: typography.sectionTitle.size,
          fontWeight: typography.sectionTitle.weight,
          lineHeight: typography.sectionTitle.lineHeight,
          color: colors.headingText,
          margin: 0,
        }}
      >
        Get Started
      </h2>

      <p
        style={{
          fontSize: typography.body.size,
          fontWeight: typography.body.weight,
          lineHeight: typography.body.lineHeight,
          color: colors.bodyText,
          margin: `${spacing.element} 0 0 0`,
        }}
      >
        Welcome to your workspace. Here are three ways to get going:
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.element, marginTop: spacing.card }}>
        {actions.map((action) => (
          <NavLink
            key={action.title}
            to={action.to}
            state={action.state}
            style={{ textDecoration: 'none', color: 'inherit' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: spacing.element,
                padding: spacing.element,
                borderRadius: '12px',
                transition: 'background 150ms ease',
              }}
              className="hover:bg-[var(--brand-tint-warmest)]"
            >
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '10px',
                  background: colors.brandTint,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <action.icon size={20} style={{ color: colors.brandCoral }} />
              </div>

              <div>
                <div
                  style={{
                    fontSize: typography.body.size,
                    fontWeight: '600',
                    lineHeight: typography.body.lineHeight,
                    color: colors.headingText,
                  }}
                >
                  {action.title}
                </div>
                <div
                  style={{
                    fontSize: typography.caption.size,
                    fontWeight: typography.caption.weight,
                    lineHeight: typography.caption.lineHeight,
                    color: colors.secondaryText,
                  }}
                >
                  {action.subtitle}
                </div>
              </div>
            </div>
          </NavLink>
        ))}
      </div>
    </BrandedCard>
  )
}
