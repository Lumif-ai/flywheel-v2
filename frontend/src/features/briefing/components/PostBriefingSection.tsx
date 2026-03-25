import { Calendar, Search, Eye, Mail } from 'lucide-react'
import { colors, typography } from '@/lib/design-tokens'

interface PostBriefingSectionProps {
  onExplore: () => void
}

const CAPABILITIES = [
  {
    icon: Calendar,
    title: 'Prep for any meeting',
    description: 'Get briefings for your upcoming meetings in seconds',
  },
  {
    icon: Search,
    title: 'Research any company',
    description: 'Deep company intelligence before you reach out',
  },
  {
    icon: Eye,
    title: 'Track competitors',
    description: 'Automatic competitive landscape monitoring',
  },
  {
    icon: Mail,
    title: 'Draft follow-up emails',
    description: 'Context-aware email drafts after every meeting',
  },
] as const

export function PostBriefingSection({ onExplore }: PostBriefingSectionProps) {
  return (
    <section
      style={{
        marginTop: '48px',
        padding: '48px 32px',
        background: 'rgba(233,77,53,0.03)',
        borderRadius: '16px',
        textAlign: 'center',
      }}
    >
      <h2
        style={{
          fontSize: typography.pageTitle.size,
          fontWeight: typography.pageTitle.weight,
          lineHeight: typography.pageTitle.lineHeight,
          letterSpacing: typography.pageTitle.letterSpacing,
          color: colors.headingText,
          margin: '0 0 8px 0',
        }}
      >
        This is just the beginning
      </h2>
      <p
        style={{
          fontSize: typography.body.size,
          lineHeight: typography.body.lineHeight,
          color: colors.secondaryText,
          margin: '0 0 32px 0',
          maxWidth: '420px',
          marginLeft: 'auto',
          marginRight: 'auto',
        }}
      >
        Imagine this for every meeting, every prospect, every deal.
      </p>

      {/* Capability cards 2x2 grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '16px',
          maxWidth: '560px',
          margin: '0 auto 32px auto',
        }}
      >
        {CAPABILITIES.map((cap) => {
          const Icon = cap.icon
          return (
            <div
              key={cap.title}
              style={{
                background: '#fff',
                borderRadius: '12px',
                border: `1px solid ${colors.subtleBorder}`,
                padding: '20px 16px',
                textAlign: 'left',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <Icon
                style={{
                  width: 20,
                  height: 20,
                  color: 'var(--brand-coral)',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: typography.body.size,
                  fontWeight: '600',
                  color: colors.headingText,
                }}
              >
                {cap.title}
              </span>
              <span
                style={{
                  fontSize: typography.caption.size,
                  lineHeight: typography.caption.lineHeight,
                  color: colors.secondaryText,
                }}
              >
                {cap.description}
              </span>
            </div>
          )
        })}
      </div>

      {/* CTA */}
      <button
        onClick={onExplore}
        style={{
          padding: '10px 28px',
          borderRadius: '999px',
          border: 'none',
          background: 'linear-gradient(135deg, var(--brand-coral), var(--brand-gradient-end))',
          color: '#fff',
          fontSize: typography.body.size,
          fontWeight: '500',
          cursor: 'pointer',
          transition: 'transform 0.15s, box-shadow 0.15s',
        }}
        onMouseEnter={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.transform = 'translateY(-1px)'
          el.style.boxShadow = '0 4px 12px rgba(233,77,53,0.3)'
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.transform = 'translateY(0)'
          el.style.boxShadow = 'none'
        }}
      >
        Explore your workspace &rarr;
      </button>
    </section>
  )
}
