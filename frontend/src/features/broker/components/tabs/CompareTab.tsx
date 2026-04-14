import { AlertTriangle } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { useBrokerProject } from '../../hooks/useBrokerProject'
import { useComparison } from '../../hooks/useBrokerQuotes'
import { ComparisonView } from '../comparison/ComparisonView'

interface CompareTabProps {
  projectId: string
}

export function CompareTab({ projectId }: CompareTabProps) {
  const { data: project } = useBrokerProject(projectId)
  const { data, isLoading, isError } = useComparison(projectId, true)

  if (isLoading) {
    return (
      <div className="space-y-4 py-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full rounded" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-dashed border-red-200 bg-red-50 p-8 text-center">
        <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-red-800">
          Failed to load comparison data
        </p>
        <p className="text-xs text-red-600 mt-1">
          Try refreshing the page or check that quotes have been extracted.
        </p>
      </div>
    )
  }

  if (!data) return null

  return (
    <ComparisonView
      data={data}
      currency={project?.currency || 'USD'}
    />
  )
}
