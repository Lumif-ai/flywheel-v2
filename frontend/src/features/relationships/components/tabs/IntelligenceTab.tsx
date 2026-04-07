import { useState } from 'react'
import { Brain, Edit2, Check, X } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BrandedCard } from '@/components/ui/branded-card'
import { EmptyState } from '@/components/ui/empty-state'
import { Textarea } from '@/components/ui/textarea'
import { updateAccount, queryKeys } from '../../api'

interface IntelligenceTabProps {
  accountId: string
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

function IntelCard({ accountId, field, intel }: { accountId: string; field: IntelField; intel: Record<string, unknown> }) {
  const [hovered, setHovered] = useState(false)
  const [editing, setEditing] = useState(false)
  const value = lookupValue(intel, field.keys)
  const [editValue, setEditValue] = useState(value ?? '')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      // Use the first key as the canonical key
      const key = field.keys[0]
      const updated = { ...intel, [key]: editValue.trim() || undefined }
      // Remove empty values
      for (const k of field.keys.slice(1)) {
        delete updated[k]
      }
      return updateAccount(accountId, { intel: updated })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.detail(accountId) })
      toast.success(`${field.label} updated`)
      setEditing(false)
    },
    onError: () => toast.error(`Failed to update ${field.label}`),
  })

  function startEdit(e: React.MouseEvent) {
    e.stopPropagation()
    setEditValue(value ?? '')
    setEditing(true)
  }

  if (editing) {
    return (
      <BrandedCard variant="info" hoverable={false}>
        <span
          className="text-xs font-semibold uppercase tracking-wider mb-1.5 block"
          style={{ color: 'var(--secondary-text)' }}
        >
          {field.label}
        </span>
        <Textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          rows={3}
          className="text-sm mb-2"
          autoFocus
        />
        <div className="flex justify-end gap-1">
          <button
            onClick={() => setEditing(false)}
            className="p-1 rounded hover:bg-muted"
            style={{ color: 'var(--secondary-text)' }}
          >
            <X className="size-4" />
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="p-1 rounded hover:bg-muted"
            style={{ color: 'var(--brand-coral)' }}
          >
            <Check className="size-4" />
          </button>
        </div>
      </BrandedCard>
    )
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
            onClick={startEdit}
            className="p-0.5 rounded transition-opacity hover:opacity-70"
            style={{ color: 'var(--secondary-text)' }}
            aria-label={`Edit ${field.label}`}
          >
            <Edit2 className="size-3.5" />
          </button>
        )}
      </div>
      {value ? (
        <p className="text-sm cursor-pointer" style={{ color: 'var(--body-text)' }} onClick={startEdit}>
          {value}
        </p>
      ) : (
        <p
          className="text-sm italic cursor-pointer"
          style={{ color: 'var(--secondary-text)' }}
          onClick={startEdit}
        >
          Not yet captured — click to add
        </p>
      )}
    </BrandedCard>
  )
}

export function IntelligenceTab({ accountId, intel }: IntelligenceTabProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {INTEL_FIELDS.map((field) => (
        <IntelCard key={field.label} accountId={accountId} field={field} intel={intel} />
      ))}
    </div>
  )
}
