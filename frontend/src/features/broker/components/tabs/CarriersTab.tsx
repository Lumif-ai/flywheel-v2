import { Building2 } from 'lucide-react'

interface CarriersTabProps {
  projectId: string
}

export function CarriersTab({ projectId: _projectId }: CarriersTabProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Building2 className="h-10 w-10 text-muted-foreground mb-3" />
      <h3 className="text-lg font-medium">Carriers</h3>
      <p className="text-sm text-muted-foreground mt-1">Coming in Phase 126</p>
    </div>
  )
}
