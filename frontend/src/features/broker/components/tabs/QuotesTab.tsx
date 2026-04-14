import { QuoteTracking } from '../QuoteTracking'

interface QuotesTabProps {
  projectId: string
}

export function QuotesTab({ projectId }: QuotesTabProps) {
  return <QuoteTracking projectId={projectId} />
}
