import { useState } from 'react'
import { Brain, Edit2 } from 'lucide-react'
import { toast } from 'sonner'
import { BrandedCard } from '@/components/ui/branded-card'
import { EmptyState } from '@/components/ui/empty-state'

interface IntelligenceTabProps {
  intel: Record<string, unknown>
}

interface IntelField {
  label: string
  keys: string[]  // possible key names to look up (case-insensitive fallback handled by lookup)
}

const INTEL_FIELDS: IntelField[] = [
  { label: 'Pain', keys: ['pain', 'Pain', 'pain_point', 'painPoint'] },
  { label: 'Budget', keys: ['budget', 'Budget', 'budget_range', 'budgetRange'] },
  { label: 'Competition', keys: ['competition', 'Competition', 'competitor', 'Competitor', 'competitors'] },
  { label: 'Champion', keys: ['champion', 'Champion', 'internal_champion', 'internalChampion'] },
  { label: 'Blocker', keys: ['blocker', 'Blocker', 'blockers', 'Blockers', 'obstacle', 'Obstacle'] },
  { label: 'Fit Reasoning', keys: ['fit_reasoning', 'fitReasoning', 'Fit Reasoning', 'fit', 'Fit'] },
]

function lookupValue(intel: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    if (key in intel && intel[key] !== null && intel[key] !== undefined && intel[key] !== '') {
      return String(intel[key])
    }
  }
  // Also do a case-insensitive pass over all intel keys
  const intelKeys = Object.keys(intel)
  for (const candidate of keys) {
    const match = intelKeys.find((k) => k.toLowerCase() === candidate.toLowerCase())
    if (match && intel[match] !== null && intel[match] !== undefined && intel[match] !== '') {
      return String(intel[match])
    }
  }
  return null
}

function IntelCard({ field, intel }: { field: IntelField; intel: Record<string, unknown> }) {
  const [hovered, setHovered] = useState(false)
  const value = lookupValue(intel, field.keys)

  function handleEdit(e: React.MouseEvent) {
    e.stopPropagation()
    toast.info('Intelligence editing coming soon')
  }

  return (
    <BrandedCard
      variant="info"
      hoverable={false}
      className="relative group/intel-card"
    >
      <div
        className="flex items-center justify-between mb-1.5"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <span
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ color: 'var(--secondary-text)' }}
        >
          {field.label}
        </span>
        {hovered && (
          <button
            onClick={handleEdit}
            className="p-0.5 rounded transition-opacity hover:opacity-70"
            style={{ color: 'var(--secondary-text)' }}
            aria-label={`Edit ${field.label}`}
          >
            <Edit2 className="size-3.5" />
          </button>
        )}
      </div>
      {value ? (
        <p className="text-sm" style={{ color: 'var(--body-text)' }}>
          {value}
        </p>
      ) : (
        <p
          className="text-sm italic"
          style={{ color: 'var(--secondary-text)' }}
        >
          Not yet captured
        </p>
      )}
    </BrandedCard>
  )
}

export function IntelligenceTab({ intel }: IntelligenceTabProps) {
  const hasAnyData = INTEL_FIELDS.some((f) => lookupValue(intel, f.keys) !== null)

  if (!hasAnyData) {
    return (
      <EmptyState
        icon={Brain}
        title="No intelligence gathered yet"
        description="Add notes to build this profile. Pain points, budget, competition, and fit reasoning will appear here."
      />
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {INTEL_FIELDS.map((field) => (
        <IntelCard key={field.label} field={field} intel={intel} />
      ))}
    </div>
  )
}
