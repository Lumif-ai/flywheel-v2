import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, Globe, Terminal } from 'lucide-react'
import { useProjectQuotes, useConfirmPortal } from '../hooks/useSolicitations'
import type { CarrierQuote } from '../types/broker'

interface PortalSubmissionProps {
  projectId: string
}

function PortalCard({
  quote,
  projectId,
}: {
  quote: CarrierQuote
  projectId: string
}) {
  const confirmPortal = useConfirmPortal(projectId)

  if (quote.draft_status === 'confirmed') {
    return (
      <div className="rounded-xl border p-4 space-y-2 bg-green-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <span className="font-medium">{quote.carrier_name}</span>
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-0 text-xs">
            Confirmed
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Confirmed {quote.solicited_at ? new Date(quote.solicited_at).toLocaleString() : ''}
        </p>
      </div>
    )
  }

  if (quote.draft_status === 'review') {
    const screenshotUrl = (quote.metadata_ as Record<string, unknown>)?.screenshot_url as string | undefined
    return (
      <div className="rounded-xl border p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-purple-500" />
            <span className="font-medium">{quote.carrier_name}</span>
          </div>
          <Badge variant="outline" className="text-xs">Review</Badge>
        </div>

        {screenshotUrl && (
          <div className="rounded-lg border overflow-hidden">
            <img
              src={screenshotUrl}
              alt={`Portal submission screenshot for ${quote.carrier_name}`}
              className="w-full h-auto max-h-64 object-contain bg-gray-50"
            />
          </div>
        )}

        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => confirmPortal.mutate(quote.id)}
            disabled={confirmPortal.isPending}
          >
            {confirmPortal.isPending ? 'Confirming...' : 'Approve & Submit'}
          </Button>
          <Button size="sm" variant="ghost">
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  // Not yet submitted (draft_status is null)
  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{quote.carrier_name}</span>
        </div>
        <Badge variant="outline" className="text-xs">Pending</Badge>
      </div>

      <div className="rounded-lg bg-muted/50 p-3 space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Terminal className="h-3.5 w-3.5" />
          <span>Run the portal submission script locally:</span>
        </div>
        <code className="block text-xs bg-muted rounded px-2 py-1.5 font-mono overflow-x-auto">
          python -m flywheel.engines.portal_submitter --project-id {quote.broker_project_id} --carrier-config-id {quote.carrier_config_id}
        </code>
      </div>
    </div>
  )
}

export function PortalSubmission({ projectId }: PortalSubmissionProps) {
  const { data: quotes } = useProjectQuotes(projectId)

  const portalQuotes = (quotes || []).filter(
    (q) => q.draft_subject == null && q.carrier_type === 'insurance' && q.carrier_config_id != null
  )

  if (portalQuotes.length === 0) return null

  const confirmedCount = portalQuotes.filter((q) => q.draft_status === 'confirmed').length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-muted-foreground">Portal Submissions</h4>
        <span className="text-sm text-muted-foreground">
          {confirmedCount}/{portalQuotes.length} confirmed
        </span>
      </div>

      <div className="space-y-3">
        {portalQuotes.map((quote) => (
          <PortalCard key={quote.id} quote={quote} projectId={projectId} />
        ))}
      </div>
    </div>
  )
}
