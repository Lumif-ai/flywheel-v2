import { useSolicitationDrafts } from '../hooks/useSolicitationDrafts'
import { useCarrierMatches } from '../hooks/useCarrierMatches'
import { EmailApproval } from './EmailApproval'
import { PortalSubmission } from './PortalSubmission'
import { CheckCircle } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface SolicitationPanelProps {
  projectId: string
}

export function SolicitationPanel({ projectId }: SolicitationPanelProps) {
  const { data: drafts, isLoading } = useSolicitationDrafts(projectId)
  const { data: matchData } = useCarrierMatches(projectId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    )
  }

  if (!drafts || drafts.length === 0) return null

  // Build carrier submission method map from carrier matches
  const carrierMethodMap: Record<string, string> = {}
  ;(matchData?.matches ?? []).forEach((m) => {
    carrierMethodMap[m.carrier_name] = m.submission_method
  })

  const emailDrafts = drafts.filter((d) => (carrierMethodMap[d.carrier_name] ?? 'email') === 'email')
  const portalDrafts = drafts.filter((d) => carrierMethodMap[d.carrier_name] === 'portal')

  const sentCount = emailDrafts.filter((d) => d.status === 'sent').length
  const confirmedCount = portalDrafts.filter(
    (d) => d.status === 'sent' || d.status === 'approved'
  ).length

  const totalCarriers = emailDrafts.length + portalDrafts.length
  const solicitedCount = sentCount + confirmedCount
  const allDone = totalCarriers > 0 && solicitedCount === totalCarriers

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Solicitation</h3>
        <span className="text-sm text-muted-foreground">
          {solicitedCount}/{totalCarriers} carriers solicited
        </span>
      </div>

      {emailDrafts.length > 0 && <EmailApproval projectId={projectId} />}

      {emailDrafts.length > 0 && portalDrafts.length > 0 && (
        <div className="border-t" />
      )}

      {portalDrafts.length > 0 && <PortalSubmission projectId={projectId} />}

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
