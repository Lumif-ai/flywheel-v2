import { useBrokerProject } from '../../hooks/useBrokerProject'
import { DeliveryPanel } from '../DeliveryPanel'
import { Skeleton } from '@/components/ui/skeleton'

interface DeliveryTabProps {
  projectId: string
}

export function DeliveryTab({ projectId }: DeliveryTabProps) {
  const { data: project, isLoading } = useBrokerProject(projectId)

  if (isLoading) {
    return (
      <div className="space-y-4 py-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full rounded" />
        ))}
      </div>
    )
  }

  if (!project) return null

  return <DeliveryPanel project={project} />
}
