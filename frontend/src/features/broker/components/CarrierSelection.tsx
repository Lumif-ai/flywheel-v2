import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Building2, Mail, Globe, Clock } from 'lucide-react'
import { useCarrierMatches } from '../hooks/useCarrierMatches'
import { useDraftSolicitations } from '../hooks/useSolicitations'
import type { CarrierMatch } from '../types/broker'

interface CarrierSelectionProps {
  projectId: string
}

function MatchScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-muted-foreground w-8">{pct}%</span>
    </div>
  )
}

function CarrierCard({
  carrier,
  selected,
  onToggle,
}: {
  carrier: CarrierMatch
  selected: boolean
  onToggle: () => void
}) {
  return (
    <div
      className={`rounded-xl border p-4 space-y-3 transition-colors ${
        selected ? 'border-blue-300 bg-blue-50/50' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <p className="font-medium">{carrier.carrier_name}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge variant="outline" className="text-xs gap-1">
                {carrier.submission_method === 'portal' ? (
                  <><Globe className="h-3 w-3" /> Portal</>
                ) : (
                  <><Mail className="h-3 w-3" /> Email</>
                )}
              </Badge>
              {carrier.avg_response_days != null && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {carrier.avg_response_days}d avg
                </span>
              )}
            </div>
          </div>
        </div>
        <Building2 className="h-5 w-5 text-muted-foreground" />
      </div>

      <MatchScoreBar score={carrier.match_score} />

      <div className="flex flex-wrap gap-1.5">
        {carrier.matched_coverages.map((c) => (
          <Badge key={c} variant="outline" className="bg-green-50 text-green-700 border-0 text-xs">
            {c}
          </Badge>
        ))}
        {carrier.unmatched_coverages.map((c) => (
          <Badge key={c} variant="outline" className="bg-gray-50 text-gray-500 border-0 text-xs">
            {c}
          </Badge>
        ))}
      </div>
    </div>
  )
}

function CarrierSection({
  title,
  matches,
  selectedIds,
  onToggle,
}: {
  title: string
  matches: CarrierMatch[]
  selectedIds: Set<string>
  onToggle: (id: string) => void
}) {
  if (matches.length === 0) return null
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      <div className="grid gap-3 sm:grid-cols-2">
        {matches.map((m) => (
          <CarrierCard
            key={m.carrier_config_id}
            carrier={m}
            selected={selectedIds.has(m.carrier_config_id)}
            onToggle={() => onToggle(m.carrier_config_id)}
          />
        ))}
      </div>
    </div>
  )
}

export function CarrierSelection({ projectId }: CarrierSelectionProps) {
  const { data, isLoading } = useCarrierMatches(projectId)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const draftMutation = useDraftSolicitations(projectId)
  const [skipped, setSkipped] = useState<Array<{ carrier: string; reason: string }>>([])

  function toggleCarrier(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!data || data.matches.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center space-y-2">
        <p className="text-muted-foreground">
          No carriers configured. Go to{' '}
          <Link to="/broker/settings/carriers" className="text-blue-600 hover:underline">
            Settings &gt; Carriers
          </Link>{' '}
          to add your first carrier.
        </p>
      </div>
    )
  }

  const insuranceMatches = data.matches.filter((m) => m.carrier_type === 'insurance')
  const suretyMatches = data.matches.filter((m) => m.carrier_type === 'surety')

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Carrier Matches</h3>

      <CarrierSection
        title="Insurance Carriers"
        matches={insuranceMatches}
        selectedIds={selectedIds}
        onToggle={toggleCarrier}
      />
      <CarrierSection
        title="Surety Carriers"
        matches={suretyMatches}
        selectedIds={selectedIds}
        onToggle={toggleCarrier}
      />

      {skipped.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">Some carriers were skipped:</p>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {skipped.map((s, i) => (
              <li key={i}>{s.carrier}: {s.reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          disabled={selectedIds.size === 0 || draftMutation.isPending}
          onClick={() =>
            draftMutation.mutate(Array.from(selectedIds), {
              onSuccess: (resp) => {
                if (resp.skipped.length > 0) setSkipped(resp.skipped)
              },
            })
          }
        >
          {draftMutation.isPending
            ? 'Creating drafts...'
            : `Proceed to Solicitation${selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}`}
        </Button>
      </div>
    </div>
  )
}
