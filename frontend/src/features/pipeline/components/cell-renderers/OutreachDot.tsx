import type { ICellRendererParams } from 'ag-grid-community'
import { typography } from '@/lib/design-tokens'
import type { PipelineItem } from '../../types/pipeline'

const STATUS_COLORS: Record<string, string> = {
  sent: '#3B82F6',
  opened: '#F97316',
  replied: '#22C55E',
  bounced: '#EF4444',
}

export function OutreachDot(props: ICellRendererParams<PipelineItem>) {
  const { data } = props
  if (!data) return null

  const status = data.last_outreach_status
  const color = status ? (STATUS_COLORS[status.toLowerCase()] ?? '#9CA3AF') : '#9CA3AF'
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'None'

  return (
    <div className="flex items-center gap-2 h-full">
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: color,
          flexShrink: 0,
          display: 'inline-block',
        }}
      />
      <span
        style={{
          fontSize: typography.caption.size,
          color: status ? 'var(--body-text)' : 'var(--secondary-text)',
        }}
      >
        {label}
      </span>
    </div>
  )
}
