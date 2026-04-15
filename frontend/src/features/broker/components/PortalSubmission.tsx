import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, Globe } from 'lucide-react'
import { useSolicitationDrafts } from '../hooks/useSolicitationDrafts'
import { useCarrierMatches } from '../hooks/useCarrierMatches'
import { useConfirmPortal } from '../hooks/useSolicitations'
import { RunInClaudeCodeButton } from './shared/RunInClaudeCodeButton'
import type { SolicitationDraft } from '../types/broker'
import { CarrierBadge } from './CarrierBadge'

interface PortalSubmissionProps {
  projectId: string
}

interface PortalCardProps {
  draft: SolicitationDraft
  portalUrl: string
  carrierConfigId: string
  projectId: string
  onConfirm: () => void
  isPending: boolean
}

function PortalCard({ draft, portalUrl, carrierConfigId, projectId, onConfirm, isPending }: PortalCardProps) {
  // Confirmed state
  if (draft.status === 'sent' || draft.status === 'approved') {
    return (
      <div className="rounded-xl border p-4 space-y-2 bg-green-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <CarrierBadge name={draft.carrier_name} size={20} />
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-0 text-xs">
            Confirmed
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Confirmed {draft.sent_at ? new Date(draft.sent_at).toLocaleString() : ''}
        </p>
      </div>
    )
  }

  // Review state — PORT-02: use draft.status === 'review'
  if (draft.status === 'review') {
    const screenshotUrl = draft.metadata_?.screenshot_url as string | undefined
    return (
      <div className="rounded-xl border p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-purple-500" />
            <CarrierBadge name={draft.carrier_name} size={20} />
          </div>
          <Badge variant="outline" className="text-xs">Review</Badge>
        </div>

        {screenshotUrl && (
          <div className="rounded-lg border overflow-hidden">
            <img
              src={screenshotUrl}
              alt={`Portal submission screenshot for ${draft.carrier_name}`}
              className="w-full h-auto max-h-64 object-contain bg-gray-50"
            />
          </div>
        )}

        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? 'Confirming...' : 'Approve & Submit'}
          </Button>
          <Button size="sm" variant="ghost">
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  // Not yet submitted — PORT-01: RunInClaudeCodeButton per carrier
  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-muted-foreground" />
          <CarrierBadge name={draft.carrier_name} size={20} />
          {portalUrl && (
            <a
              href={portalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[#E94D35] hover:underline"
            >
              {portalUrl}
            </a>
          )}
        </div>
        <Badge variant="outline" className="text-xs">Pending</Badge>
      </div>
      <RunInClaudeCodeButton
        command={`claude "Submit portal application for ${draft.carrier_name}" --project-id ${projectId} --carrier-config-id ${carrierConfigId}`}
        label={`Submit ${draft.carrier_name} Portal`}
        variant="prominent"
        description="Runs Claude Code to auto-fill and submit the carrier portal application"
      />
    </div>
  )
}

export function PortalSubmission({ projectId }: PortalSubmissionProps) {
  const { data: drafts } = useSolicitationDrafts(projectId)
  const { data: matchData } = useCarrierMatches(projectId)
  const confirmPortal = useConfirmPortal(projectId)

  // Build lookup maps from carrier matches
  const portalUrlMap: Record<string, string> = {}
  const carrierConfigIdMap: Record<string, string> = {}
  ;(matchData?.matches ?? []).forEach(m => {
    if (m.portal_url) portalUrlMap[m.carrier_name] = m.portal_url
    if (m.carrier_config_id) carrierConfigIdMap[m.carrier_name] = m.carrier_config_id
  })

  // Portal drafts = solicitation drafts for carriers with a portal URL
  const portalDrafts = (drafts ?? []).filter(d => !!portalUrlMap[d.carrier_name])

  if (portalDrafts.length === 0) return null

  const confirmedCount = portalDrafts.filter(d => d.status === 'sent' || d.status === 'approved').length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-muted-foreground">Portal Submissions</h4>
        <span className="text-sm text-muted-foreground">
          {confirmedCount}/{portalDrafts.length} confirmed
        </span>
      </div>

      <div className="space-y-3">
        {portalDrafts.map((draft) => (
          <PortalCard
            key={draft.id}
            draft={draft}
            portalUrl={portalUrlMap[draft.carrier_name] ?? ''}
            carrierConfigId={carrierConfigIdMap[draft.carrier_name] ?? ''}
            projectId={projectId}
            onConfirm={() => confirmPortal.mutate(draft.carrier_quote_id)}
            isPending={confirmPortal.isPending}
          />
        ))}
      </div>
    </div>
  )
}
