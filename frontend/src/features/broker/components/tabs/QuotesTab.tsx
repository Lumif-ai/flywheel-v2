import { QuoteTracking } from '../QuoteTracking'
import type { ProjectCoverage } from '../../types/broker'

interface QuotesTabProps {
  projectId: string
  coverages: ProjectCoverage[]
}

export function QuotesTab({ projectId, coverages }: QuotesTabProps) {
  return <QuoteTracking projectId={projectId} coverages={coverages} />
}
