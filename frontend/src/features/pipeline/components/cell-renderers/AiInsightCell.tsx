import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

export function AiInsightCell(props: ICellRendererParams<PipelineListItem>) {
  const { value } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '12px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  return (
    <div className="flex items-center h-full" style={{ minWidth: 0 }}>
      <span
        style={{
          fontSize: '12px',
          color: '#6B7280',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          display: 'block',
          width: '100%',
        }}
      >
        {value}
      </span>
    </div>
  )
}
