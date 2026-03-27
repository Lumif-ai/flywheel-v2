import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineItem } from '../../types/pipeline'

export function DaysSinceCell(props: ICellRendererParams<PipelineItem>) {
  const { data } = props
  if (!data) return null

  const days = data.days_since_last_outreach

  if (days == null) {
    return (
      <div className="flex items-center h-full">
        <span style={{ color: 'var(--secondary-text)' }}>&mdash;</span>
      </div>
    )
  }

  let color = '#22C55E' // green <7d
  if (days >= 7 && days <= 14) color = '#F59E0B' // amber
  if (days > 14) color = '#EF4444' // red

  return (
    <div className="flex items-center h-full">
      <span style={{ color, fontWeight: '500', fontSize: '14px' }}>{days}d</span>
    </div>
  )
}
