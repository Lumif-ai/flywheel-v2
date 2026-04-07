import { Mail, Linkedin, ChevronDown } from 'lucide-react'
import { STAGE_COLORS } from '../types/lead'
import type { LeadContact } from '../types/lead'
import { MessageThread } from './MessageThread'

interface ContactCardProps {
  contact: LeadContact
  isExpanded: boolean
  onToggle: () => void
}

export function ContactCard({ contact, isExpanded, onToggle }: ContactCardProps) {
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const initials = contact.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  const stageColor = STAGE_COLORS[contact.pipeline_stage?.toLowerCase()] ?? '#6b7280'

  return (
    <div
      style={{
        borderBottom: '1px solid var(--subtle-border)',
      }}
      className="last:border-b-0"
    >
      {/* Header (clickable) */}
      <button
        onClick={onToggle}
        role="button"
        aria-expanded={isExpanded}
        aria-label={`${contact.name}, ${contact.title ?? 'No title'}, click to expand`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          width: '100%',
          padding: '12px 16px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(0,0,0,0.02)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'none'
        }}
      >
        {/* Avatar */}
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'var(--brand-tint)',
            color: 'var(--brand-coral)',
            fontSize: '13px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {initials}
        </div>

        {/* Name, title, role */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--heading-text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {contact.name}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
            {contact.title && (
              <span
                style={{
                  fontSize: '12px',
                  color: 'var(--secondary-text)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {contact.title}
              </span>
            )}
            {contact.role && (
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 500,
                  color: 'var(--secondary-text)',
                  background: 'var(--brand-tint)',
                  borderRadius: '9999px',
                  padding: '1px 6px',
                  whiteSpace: 'nowrap',
                }}
              >
                {contact.role}
              </span>
            )}
          </div>
        </div>

        {/* Stage badge + chevron */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          {contact.pipeline_stage && (
            <span
              aria-label={`${contact.pipeline_stage} stage`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '12px',
                fontWeight: 500,
                color: stageColor,
                textTransform: 'capitalize',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: stageColor,
                  flexShrink: 0,
                }}
              />
              {contact.pipeline_stage}
            </span>
          )}
          <ChevronDown
            style={{
              width: '16px',
              height: '16px',
              color: 'var(--secondary-text)',
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: prefersReducedMotion ? 'none' : 'transform 200ms ease',
              flexShrink: 0,
            }}
          />
        </div>
      </button>

      {/* Expandable content */}
      <div
        style={{
          display: 'grid',
          gridTemplateRows: isExpanded ? '1fr' : '0fr',
          transition: prefersReducedMotion ? 'none' : 'grid-template-rows 150ms ease',
        }}
      >
        <div style={{ overflow: 'hidden' }}>
          <div style={{ padding: '0 16px 12px 64px' }}>
            {/* Contact details */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '12px' }}>
              {contact.email && (
                <a
                  href={`mailto:${contact.email}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--info, #3b82f6)',
                    textDecoration: 'none',
                  }}
                >
                  <Mail style={{ width: '12px', height: '12px' }} />
                  {contact.email}
                </a>
              )}
              {contact.linkedin_url && (
                <a
                  href={contact.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--info, #3b82f6)',
                    textDecoration: 'none',
                  }}
                >
                  <Linkedin style={{ width: '12px', height: '12px' }} />
                  LinkedIn
                </a>
              )}
            </div>

            {/* Messages */}
            {contact.messages && contact.messages.length > 0 ? (
              <MessageThread messages={contact.messages} />
            ) : (
              <p
                style={{
                  fontSize: '13px',
                  color: 'var(--secondary-text)',
                  margin: 0,
                }}
              >
                No outreach messages yet
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
