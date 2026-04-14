import { Shield } from 'lucide-react'

interface CoverageTabProps {
  projectId: string
}

export function CoverageTab({ projectId: _projectId }: CoverageTabProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Shield className="h-10 w-10 text-muted-foreground mb-3" />
      <h3 className="text-lg font-medium">Coverage</h3>
      <p className="text-sm text-muted-foreground mt-1">Coming in Phase 126</p>
    </div>
  )
}
