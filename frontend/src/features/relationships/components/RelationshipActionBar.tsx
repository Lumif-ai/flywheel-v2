import { Send, Search, Calendar, Briefcase, Users } from 'lucide-react'
import { toast } from 'sonner'
import type { RelationshipType } from '../types/relationships'

interface ActionConfig {
  label: string
  icon: React.ElementType
}

const ACTION_CONFIG: Record<RelationshipType, ActionConfig[]> = {
  prospect: [
    { label: 'Draft Follow-up', icon: Send },
    { label: 'Research', icon: Search },
    { label: 'Schedule', icon: Calendar },
  ],
  customer: [
    { label: 'Draft Check-in', icon: Send },
    { label: 'Prep Meeting', icon: Briefcase },
    { label: 'Research', icon: Search },
  ],
  advisor: [
    { label: 'Draft Thank You', icon: Send },
    { label: 'Schedule Catch-up', icon: Calendar },
    { label: 'Ask for Intro', icon: Users },
  ],
  investor: [
    { label: 'Draft Update', icon: Send },
    { label: 'Schedule', icon: Calendar },
    { label: 'Prep Board Deck', icon: Briefcase },
  ],
}

interface RelationshipActionBarProps {
  type: RelationshipType
  accountId: string
  accountName: string
}

export function RelationshipActionBar({
  type,
  accountId: _accountId,
  accountName,
}: RelationshipActionBarProps) {
  const actions = ACTION_CONFIG[type] ?? ACTION_CONFIG.prospect

  return (
    <div
      className="sticky bottom-0 py-3 px-6"
      style={{
        background: 'var(--card-bg)',
        borderTop: '1px solid var(--subtle-border)',
        boxShadow: '0 -2px 8px rgba(0,0,0,0.04)',
      }}
    >
      <div className="flex items-center gap-3 flex-wrap">
        {actions.map(({ label, icon: Icon }) => (
          <button
            key={label}
            onClick={() => toast.info(`${label} for ${accountName} — coming soon`)}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-70"
            style={{ color: 'var(--brand-coral)' }}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
