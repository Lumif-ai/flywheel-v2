import { Badge } from '@/components/ui/badge'
import type { BrokerProjectStatus } from '../types/broker'

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  new_request: {
    label: 'New Request',
    className: 'bg-gray-100 text-gray-700 border-gray-200',
  },
  analyzing: {
    label: 'Analyzing',
    className: 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse',
  },
  analysis_failed: {
    label: 'Analysis Failed',
    className: 'bg-red-50 text-red-700 border-red-200',
  },
  gaps_identified: {
    label: 'Gaps Identified',
    className: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  },
  soliciting: {
    label: 'Soliciting',
    className: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  quotes_partial: {
    label: 'Quotes Partial',
    className: 'bg-teal-50 text-teal-700 border-teal-200',
  },
  quotes_complete: {
    label: 'Quotes Complete',
    className: 'bg-green-50 text-green-700 border-green-200',
  },
  recommended: {
    label: 'Recommended',
    className: 'bg-purple-100 text-purple-700 border-purple-200',
  },
  delivered: {
    label: 'Delivered',
    className: 'bg-green-100 text-green-700 border-green-200',
  },
  bound: {
    label: 'Bound',
    className: 'bg-green-100 text-green-800 border-green-300',
  },
  cancelled: {
    label: 'Cancelled',
    className: 'bg-gray-100 text-gray-500 border-gray-200 line-through',
  },
}

export function StatusBadge({ status }: { status: BrokerProjectStatus | string }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status.replace(/_/g, ' '),
    className: 'bg-gray-100 text-gray-600 border-gray-200',
  }

  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  )
}
