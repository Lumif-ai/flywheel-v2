import { CarrierSelection } from '../CarrierSelection'
import { SolicitationPanel } from '../SolicitationPanel'

interface CarriersTabProps {
  projectId: string
}

export function CarriersTab({ projectId }: CarriersTabProps) {
  return (
    <div className="space-y-6">
      <CarrierSelection projectId={projectId} />
      <SolicitationPanel projectId={projectId} />
    </div>
  )
}
