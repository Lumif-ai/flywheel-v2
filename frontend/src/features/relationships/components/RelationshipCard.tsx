import { useNavigate } from 'react-router'
import { Users } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import type { RelationshipListItem, RelationshipType } from '../types/relationships'

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMs < 60000) return 'just now'
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('')
}

interface RelationshipCardProps {
  item: RelationshipListItem
  type: RelationshipType
}

export function RelationshipCard({ item, type }: RelationshipCardProps) {
  const navigate = useNavigate()
  const variant = item.signal_count > 0 ? 'action' : 'info'

  const handleClick = () => {
    navigate(`/relationships/${item.id}?fromType=${type}`)
  }

  return (
    <BrandedCard variant={variant} onClick={handleClick} className="transition-interactive flex flex-col gap-3">
      {/* Top row: Avatar + name + domain */}
      <div className="flex items-center gap-3 min-w-0">
        <Avatar size="default">
          <AvatarFallback
            style={{ background: 'var(--brand-light)', color: 'var(--brand-coral)', fontSize: '13px', fontWeight: 600 }}
          >
            {getInitials(item.name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p style={{ fontWeight: 600, fontSize: '15px', color: 'var(--heading-text)', lineHeight: 1.3 }} className="truncate">
            {item.name}
          </p>
          {item.domain && (
            <p
              className="truncate"
              style={{ fontSize: '13px', color: 'var(--secondary-text)', lineHeight: 1.4 }}
            >
              {item.domain}
            </p>
          )}
        </div>
      </div>

      {/* Middle row: status badge + entity level */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="badge-translucent"
          style={{
            background: 'rgba(233, 77, 53, 0.08)',
            color: '#E94D35',
            fontSize: '12px',
            fontWeight: 500,
            padding: '2px 8px',
            borderRadius: '9999px',
          }}
        >
          {item.relationship_status}
        </span>
        <span
          style={{ fontSize: '12px', color: 'var(--secondary-text)', textTransform: 'capitalize' }}
        >
          {item.entity_level}
        </span>
      </div>

      {/* AI summary preview */}
      {item.ai_summary && (
        <p
          className="line-clamp-2"
          style={{ fontSize: '13px', color: 'var(--secondary-text)', lineHeight: 1.5 }}
        >
          {item.ai_summary.length > 120 ? item.ai_summary.slice(0, 120) + '…' : item.ai_summary}
        </p>
      )}

      {/* Bottom row: contact, time, signal badge */}
      <div className="flex items-center gap-3 flex-wrap mt-auto">
        {item.primary_contact_name && (
          <span className="flex items-center gap-1" style={{ fontSize: '12px', color: 'var(--secondary-text)' }}>
            <Users className="size-3 shrink-0" />
            {item.primary_contact_name}
          </span>
        )}
        <span style={{ fontSize: '12px', color: 'var(--secondary-text)' }}>
          {formatTimeAgo(item.last_interaction_at)}
        </span>
        {item.signal_count > 0 && (
          <span
            style={{
              background: 'rgba(233, 77, 53, 0.1)',
              color: '#E94D35',
              fontSize: '11px',
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: '9999px',
            }}
          >
            {item.signal_count} signal{item.signal_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </BrandedCard>
  )
}
