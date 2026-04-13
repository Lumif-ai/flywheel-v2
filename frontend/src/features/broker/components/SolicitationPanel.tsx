import { useProjectQuotes } from '../hooks/useSolicitations'
import { EmailApproval } from './EmailApproval'
import { PortalSubmission } from './PortalSubmission'
import { CheckCircle } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface SolicitationPanelProps {
  projectId: string
}

export function SolicitationPanel({ projectId }: SolicitationPanelProps) {
  const { data: quotes, isLoading } = useProjectQuotes(projectId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    )
  }

  if (!quotes || quotes.length === 0) return null

  const emailQuotes = quotes.filter((q) => q.draft_subject != null)
  const portalQuotes = quotes.filter(
    (q) => q.draft_subject == null && q.carrier_config_id != null
  )

  const totalCarriers = emailQuotes.length + portalQuotes.length
  const solicitedCount =
    emailQuotes.filter((q) => q.draft_status === 'sent').length +
    portalQuotes.filter((q) => q.draft_status === 'confirmed').length

  const allDone = totalCarriers > 0 && solicitedCount === totalCarriers

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Solicitation</h3>
        <span className="text-sm text-muted-foreground">
          {solicitedCount}/{totalCarriers} carriers solicited
        </span>
      </div>

      {emailQuotes.length > 0 && <EmailApproval projectId={projectId} />}

      {emailQuotes.length > 0 && portalQuotes.length > 0 && (
        <div className="border-t" />
      )}

      {portalQuotes.length > 0 && <PortalSubmission projectId={projectId} />}

      {allDone && (
        <div className="rounded-lg bg-green-50 p-4 flex items-center gap-3 text-green-700">
          <CheckCircle className="h-5 w-5" />
          <p className="text-sm font-medium">
            All carriers solicited. Project status will update automatically.
          </p>
        </div>
      )}
    </div>
  )
}
