import { BarChart3 } from 'lucide-react'

interface CompareTabProps {
  projectId: string
}

export function CompareTab({ projectId: _projectId }: CompareTabProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <BarChart3 className="h-10 w-10 text-muted-foreground mb-3" />
      <h3 className="text-lg font-medium">Compare</h3>
      <p className="text-sm text-muted-foreground mt-1">Coming in Phase 127</p>
    </div>
  )
}
