import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

const STAGE_COLORS: Record<string, { bg: string; text: string }> = {
  identified: { bg: '#F3F4F6', text: '#6B7280' },
  contacted: { bg: '#DBEAFE', text: '#2563EB' },
  engaged: { bg: '#FEF3C7', text: '#D97706' },
  qualified: { bg: '#D1FAE5', text: '#059669' },
  committed: { bg: '#EDE9FE', text: '#7C3AED' },
  closed: { bg: 'rgba(233,77,53,0.1)', text: '#E94D35' },
}

export function StagePill(props: ICellRendererParams<PipelineListItem>) {
  const { value } = props
  if (!value) return null

  const stage = String(value).toLowerCase()
  const colors = STAGE_COLORS[stage] ?? { bg: '#F3F4F6', text: '#6B7280' }

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-block',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'capitalize',
          background: colors.bg,
          color: colors.text,
        }}
      >
        {stage}
      </span>
    </div>
  )
}
