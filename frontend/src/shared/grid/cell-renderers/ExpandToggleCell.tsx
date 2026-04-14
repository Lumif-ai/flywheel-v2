import { ChevronRight, ChevronDown } from 'lucide-react'
import type { ICellRendererParams } from 'ag-grid-community'

interface ExpandToggleCellProps extends ICellRendererParams {
  expandedIds: Set<string>
  onToggle: (id: string) => void
}

export function ExpandToggleCell(props: ExpandToggleCellProps) {
  const { data } = props
  if (!data || data._isDetailRow) return null

  const isExpanded = props.expandedIds?.has(data.id) ?? false
  const Icon = isExpanded ? ChevronDown : ChevronRight

  return (
    <div
      className="flex items-center justify-center h-full cursor-pointer"
      onClick={(e) => {
        e.stopPropagation()
        props.onToggle?.(data.id)
      }}
    >
      <Icon size={16} style={{ color: '#6B7280' }} />
    </div>
  )
}
