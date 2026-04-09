import { useState } from 'react'
import { Link } from 'react-router'
import { Globe, Pencil } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { typography } from '@/lib/design-tokens'
import type { RelationshipDetailItem, RelationshipType } from '../types/relationships'
import { EditAccountDialog } from './EditAccountDialog'

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

function statusColor(status: string): React.CSSProperties {
  switch (status) {
    case 'active':
      return { background: 'rgba(34,197,94,0.1)', color: '#16a34a' }
    case 'at_risk':
      return { background: 'rgba(245,158,11,0.1)', color: '#d97706' }
    case 'churned':
      return { background: 'rgba(239,68,68,0.1)', color: '#dc2626' }
    default:
      return { background: 'rgba(107,114,128,0.1)', color: '#6b7280' }
  }
}

interface RelationshipHeaderProps {
  account: RelationshipDetailItem
  fromType: RelationshipType
}

const TYPE_TO_PLURAL: Record<RelationshipType, string> = {
  prospect: 'prospects',
  customer: 'customers',
  advisor: 'advisors',
  investor: 'investors',
}

export function RelationshipHeader({ account, fromType }: RelationshipHeaderProps) {
  const initials = getInitials(account.name)
  const [editOpen, setEditOpen] = useState(false)

  return (
    <div className="flex flex-col sm:flex-row items-start gap-4 mb-6">
      {/* Avatar */}
      <Avatar size="xl" className="shrink-0">
        <AvatarFallback
          style={{
            background: 'rgba(233,77,53,0.12)',
            color: '#E94D35',
            fontWeight: 600,
          }}
        >
          {initials}
        </AvatarFallback>
      </Avatar>

      {/* Text content */}
      <div className="flex-1 min-w-0">
        {/* Name + Edit button */}
        <div className="flex items-center gap-2">
          <h1
            className="text-foreground"
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
            }}
          >
            {account.name}
          </h1>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setEditOpen(true)}
            className="opacity-50 hover:opacity-100 transition-opacity"
          >
            <Pencil className="size-3.5" />
          </Button>
        </div>

        <EditAccountDialog account={account} open={editOpen} onOpenChange={setEditOpen} />

        {/* Domain */}
        {account.domain && (
          <a
            href={`https://${account.domain}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors mt-0.5"
          >
            <Globe className="size-3.5" />
            {account.domain}
          </a>
        )}

        {/* Type badges + entity level row */}
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {account.relationship_type.map((type) => {
            const plural = TYPE_TO_PLURAL[type as RelationshipType] ?? `${type}s`
            const isActive = type === fromType
            return (
              <Link
                key={type}
                to={`/relationships/${plural}`}
                className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors hover:opacity-80"
                style={{
                  background: isActive
                    ? 'rgba(233,77,53,0.2)'
                    : 'rgba(233,77,53,0.1)',
                  color: '#E94D35',
                }}
              >
                {capitalize(type)}
              </Link>
            )
          })}

          {/* Entity type */}
          <span className="text-xs text-muted-foreground">
            {capitalize(account.entity_type)}
          </span>

          {/* Stage */}
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
            style={statusColor(account.stage)}
          >
            {account.stage.replace(/_/g, ' ')}
          </span>
        </div>
      </div>
    </div>
  )
}
