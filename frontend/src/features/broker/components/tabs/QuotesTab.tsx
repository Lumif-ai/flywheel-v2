import { Receipt } from 'lucide-react'

interface QuotesTabProps {
  projectId: string
}

export function QuotesTab({ projectId: _projectId }: QuotesTabProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Receipt className="h-10 w-10 text-muted-foreground mb-3" />
      <h3 className="text-lg font-medium">Quotes</h3>
      <p className="text-sm text-muted-foreground mt-1">Coming in Phase 127</p>
    </div>
  )
}
