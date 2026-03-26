import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { typography } from '@/lib/design-tokens'
import { Linkedin, Mail } from 'lucide-react'
import type { ContactResponse } from '../types/accounts'

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

interface ContactsPanelProps {
  contacts: ContactResponse[]
}

export function ContactsPanel({ contacts }: ContactsPanelProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h2
          className="text-foreground"
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
          }}
        >
          Contacts
        </h2>
        <Badge variant="secondary">{contacts.length}</Badge>
      </div>

      {contacts.length === 0 ? (
        <p className="text-muted-foreground text-sm">No contacts yet</p>
      ) : (
        <ScrollArea className="max-h-[400px]">
          <div className="space-y-3 pr-2">
            {contacts.map((contact) => (
              <div
                key={contact.id}
                className="flex items-start gap-3 rounded-lg border border-border p-3"
              >
                <Avatar size="default">
                  <AvatarFallback>{getInitials(contact.name)}</AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-foreground truncate">
                    {contact.name}
                  </p>
                  {contact.title && (
                    <p className="text-xs text-muted-foreground truncate">
                      {contact.title}
                    </p>
                  )}
                  {contact.role_in_deal && (
                    <Badge variant="outline" className="mt-1 text-[10px]">
                      {contact.role_in_deal}
                    </Badge>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    {contact.email && (
                      <a
                        href={`mailto:${contact.email}`}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        title={contact.email}
                      >
                        <Mail className="size-3.5" />
                      </a>
                    )}
                    {contact.linkedin_url && (
                      <a
                        href={contact.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        title="LinkedIn profile"
                      >
                        <Linkedin className="size-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  )
}
