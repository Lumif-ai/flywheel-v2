import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

const STATUS_PRIORITY = ['replied', 'sent', 'drafted'] as const
const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  replied: { bg: '#DCFCE7', text: '#166534' },
  sent: { bg: '#DBEAFE', text: '#1E40AF' },
  drafted: { bg: '#F3F4F6', text: '#6B7280' },
}

export function OutreachStatusCell(props: ICellRendererParams<PipelineListItem>) {
  const summary = props.data?.outreach_summary
  if (!summary || Object.keys(summary).length === 0) {
    return <span style={{ color: '#D1D5DB', fontSize: '12px' }}>—</span>
  }

  // Show the most advanced status first
  const topStatus = STATUS_PRIORITY.find((s) => summary[s] && summary[s] > 0)
  if (!topStatus) return <span style={{ color: '#D1D5DB', fontSize: '12px' }}>—</span>

  const count = summary[topStatus]
  const colors = STATUS_COLORS[topStatus] ?? STATUS_COLORS.drafted

  // Build summary text: "5 drafted" or "2 sent, 5 drafted"
  const parts: string[] = []
  for (const s of STATUS_PRIORITY) {
    if (summary[s]) parts.push(`${summary[s]} ${s}`)
  }

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 500,
          background: colors.bg,
          color: colors.text,
        }}
        title={parts.join(', ')}
      >
        {count} {topStatus}
      </span>
    </div>
  )
}
