import { Users, Linkedin } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { BrandedCard } from '@/components/ui/branded-card'
import { EmptyState } from '@/components/ui/empty-state'
import type { ContactItem } from '../../types/relationships'

interface PeopleTabProps {
  contacts: ContactItem[]
}

function daysAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDay = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDay === 0) return 'today'
  if (diffDay === 1) return '1 day ago'
  if (diffDay < 30) return `${diffDay} days ago`
  const diffWeek = Math.floor(diffDay / 7)
  if (diffWeek < 5) return `${diffWeek} weeks ago`
  const diffMonth = Math.floor(diffDay / 30)
  if (diffMonth < 12) return `${diffMonth} months ago`
  return `${Math.floor(diffMonth / 12)} years ago`
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0].toUpperCase())
    .slice(0, 2)
    .join('')
}

function ContactCard({ contact }: { contact: ContactItem }) {
  const initials = getInitials(contact.name)

  return (
    <BrandedCard variant="info" hoverable={false}>
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <Avatar size="xl" className="shrink-0">
          <AvatarFallback
            className="text-sm font-semibold"
            style={{
              background: 'var(--brand-tint)',
              color: 'var(--brand-coral)',
            }}
          >
            {initials}
          </AvatarFallback>
        </Avatar>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-sm font-semibold"
              style={{ color: 'var(--heading-text)' }}
            >
              {contact.name}
            </span>
            {/* Role badge */}
            {contact.role && (
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                style={{
                  background: 'rgba(233, 77, 53, 0.1)',
                  color: 'var(--brand-coral)',
                }}
              >
                {contact.role}
              </span>
            )}
          </div>

          {contact.title && (
            <p
              className="text-xs mt-0.5"
              style={{ color: 'var(--secondary-text)' }}
            >
              {contact.title}
            </p>
          )}

          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            {contact.email && (
              <a
                href={`mailto:${contact.email}`}
                className="text-xs transition-opacity hover:opacity-70"
                style={{ color: 'var(--brand-coral)' }}
                onClick={(e) => e.stopPropagation()}
              >
                {contact.email}
              </a>
            )}

            {contact.linkedin_url && (
              <a
                href={contact.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs transition-opacity hover:opacity-70"
                style={{ color: 'var(--secondary-text)' }}
                onClick={(e) => e.stopPropagation()}
              >
                <Linkedin className="size-3.5" />
                LinkedIn
              </a>
            )}
          </div>

          <p
            className="text-xs mt-1.5"
            style={{ color: 'var(--secondary-text)' }}
          >
            Added {daysAgo(contact.created_at)}
          </p>
        </div>
      </div>
    </BrandedCard>
  )
}

export function PeopleTab({ contacts }: PeopleTabProps) {
  if (contacts.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No contacts found"
        description="Contacts associated with this account will appear here once they are added."
      />
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {contacts.map((contact) => (
        <ContactCard key={contact.id} contact={contact} />
      ))}
    </div>
  )
}
