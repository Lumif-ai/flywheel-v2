import { useEffect, useRef, useState } from 'react'
import { X, Globe, Mail, Linkedin } from 'lucide-react'
import { MessageThread } from './MessageThread'
import { STAGE_COLORS } from '../types/lead'
import { badges } from '@/lib/design-tokens'
import type { LeadRow } from '../types/lead'

interface LeadSidePanelProps {
  row: LeadRow
  onClose: () => void
}

export function LeadSidePanel({ row, onClose }: LeadSidePanelProps) {
  const [isVisible, setIsVisible] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<Element | null>(null)

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    previousFocusRef.current = document.activeElement
    requestAnimationFrame(() => setIsVisible(true))
    if (panelRef.current) panelRef.current.focus()
    return () => {
      if (previousFocusRef.current instanceof HTMLElement) previousFocusRef.current.focus()
    }
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const stageColor = STAGE_COLORS[row.contact_stage?.toLowerCase()] ?? '#9CA3AF'
  const tierKey = (row.fit_tier?.toLowerCase() ?? '') as keyof typeof badges.fitTier
  const tierColors = badges.fitTier[tierKey] ?? { bg: 'rgba(107,114,128,0.06)', text: '#6b7280' }
  const initials = row.contact_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)

  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="dialog"
      aria-label={`${row.contact_name} details`}
      style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: '440px', zIndex: 40,
        borderLeft: '1px solid var(--subtle-border)',
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        display: 'flex', flexDirection: 'column', height: '100vh',
        background: 'var(--card-bg)',
        transform: prefersReducedMotion ? 'none' : isVisible ? 'translateX(0)' : 'translateX(100%)',
        transition: prefersReducedMotion ? 'none' : 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        outline: 'none',
      }}
    >
      {/* Header — person */}
      <div style={{ flexShrink: 0, padding: '16px 24px', borderBottom: '1px solid var(--subtle-border)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: 40, height: 40, borderRadius: '50%', background: 'var(--brand-tint)', color: 'var(--brand-coral)',
          fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--heading-text)', margin: 0 }}>{row.contact_name}</h2>
          {row.title && <p style={{ fontSize: '13px', color: 'var(--secondary-text)', margin: '2px 0 0' }}>{row.title}</p>}
        </div>
        <button onClick={onClose} aria-label="Close panel" style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28,
          borderRadius: '6px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--secondary-text)',
        }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'none' }}
        >
          <X style={{ width: 20, height: 20 }} />
        </button>
      </div>

      {/* Contact info + company */}
      <div style={{ flexShrink: 0, padding: '16px 24px', borderBottom: '1px solid var(--subtle-border)' }}>
        {/* Contact links */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {row.email && (
            <a href={`mailto:${row.email}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--info, #3b82f6)', textDecoration: 'none' }}>
              <Mail style={{ width: 12, height: 12 }} /> {row.email}
            </a>
          )}
          {row.linkedin_url && (
            <a href={row.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--info, #3b82f6)', textDecoration: 'none' }}>
              <Linkedin style={{ width: 12, height: 12 }} /> LinkedIn
            </a>
          )}
        </div>

        {/* Company + badges row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--heading-text)' }}>{row.company_name}</span>
          {row.domain && (
            <a href={`https://${row.domain}`} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '12px', color: 'var(--secondary-text)', textDecoration: 'none' }}>
              <Globe style={{ width: 12, height: 12 }} /> {row.domain}
            </a>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', fontWeight: 500, color: stageColor, textTransform: 'capitalize' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: stageColor }} />
            {row.contact_stage}
          </span>
          {row.fit_tier && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 500, color: tierColors.text }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: tierColors.text, opacity: 0.7 }} />
              {row.fit_tier}
            </span>
          )}
          {row.role && (
            <span style={{ fontSize: '10px', fontWeight: 500, color: 'var(--secondary-text)', background: 'var(--brand-tint)', borderRadius: '9999px', padding: '1px 6px' }}>
              {row.role}
            </span>
          )}
          {row.purpose.map((p) => (
            <span key={p} style={{ fontSize: '11px', color: 'var(--secondary-text)' }}>{p}</span>
          ))}
        </div>

        {row.fit_rationale && (
          <p style={{ fontSize: '13px', color: 'var(--secondary-text)', fontStyle: 'italic', marginTop: '8px', marginBottom: 0, lineHeight: 1.5 }}>
            {row.fit_rationale}
          </p>
        )}
      </div>

      {/* Messages section */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--heading-text)' }}>Messages</span>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--secondary-text)', background: 'var(--brand-tint)', borderRadius: '9999px', padding: '1px 8px', minWidth: '20px', textAlign: 'center' }}>
            {row.messages.length}
          </span>
        </div>

        {row.messages.length > 0 ? (
          <MessageThread messages={row.messages} />
        ) : (
          <p style={{ fontSize: '13px', color: 'var(--secondary-text)', textAlign: 'center', padding: '24px 0', margin: 0 }}>
            No outreach messages yet
          </p>
        )}
      </div>

    </div>
  )
}
