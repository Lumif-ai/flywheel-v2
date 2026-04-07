import { useState } from 'react'
import { Users, Linkedin, Pencil, Plus, Trash2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { BrandedCard } from '@/components/ui/branded-card'
import { EmptyState } from '@/components/ui/empty-state'
import { deleteContact, queryKeys } from '../../api'
import { EditContactDialog } from '../EditContactDialog'
import type { ContactItem } from '../../types/relationships'

interface PeopleTabProps {
  accountId: string
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

function ContactCard({ accountId, contact }: { accountId: string; contact: ContactItem }) {
  const initials = getInitials(contact.name)
  const [editOpen, setEditOpen] = useState(false)
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(accountId, contact.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.detail(accountId) })
      toast.success('Contact removed')
    },
  })

  return (
    <>
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

            <div className="flex items-center gap-2 mt-1.5">
              <p
                className="text-xs flex-1"
                style={{ color: 'var(--secondary-text)' }}
              >
                Added {daysAgo(contact.created_at)}
              </p>
              <button
                onClick={() => setEditOpen(true)}
                className="p-1 rounded opacity-0 group-hover/card:opacity-60 hover:!opacity-100 transition-opacity"
                style={{ color: 'var(--secondary-text)' }}
              >
                <Pencil className="size-3" />
              </button>
              <button
                onClick={() => {
                  if (confirm(`Remove ${contact.name}?`)) deleteMutation.mutate()
                }}
                className="p-1 rounded opacity-0 group-hover/card:opacity-60 hover:!opacity-100 transition-opacity"
                style={{ color: 'var(--secondary-text)' }}
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          </div>
        </div>
      </BrandedCard>

      <EditContactDialog
        accountId={accountId}
        contact={contact}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
    </>
  )
}

export function PeopleTab({ accountId, contacts }: PeopleTabProps) {
  const [addOpen, setAddOpen] = useState(false)

  return (
    <div>
      <div className="flex justify-end mb-3">
        <Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-3.5 mr-1" />
          Add Contact
        </Button>
      </div>

      {contacts.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No contacts found"
          description="Contacts associated with this account will appear here once they are added."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {contacts.map((contact) => (
            <div key={contact.id} className="group/card">
              <ContactCard accountId={accountId} contact={contact} />
            </div>
          ))}
        </div>
      )}

      <EditContactDialog
        accountId={accountId}
        contact={null}
        open={addOpen}
        onOpenChange={setAddOpen}
      />
    </div>
  )
}
