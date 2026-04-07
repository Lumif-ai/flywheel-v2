import type { ICellRendererParams } from 'ag-grid-community'
import type { ContactListItem } from '../../types/pipeline'
import { ACTIVITY_STATUS_COLORS } from '../../constants'

export function ContactStatusPill(props: ICellRendererParams<ContactListItem>) {
  const { value } = props
  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ color: '#9CA3AF' }}>&mdash;</span>
      </div>
    )
  }

  const status = String(value).toLowerCase()
  const colors = ACTIVITY_STATUS_COLORS[status] ?? { bg: '#F3F4F6', text: '#6B7280' }

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '1px 6px',
          borderRadius: '4px',
          fontSize: '11px',
          fontWeight: 500,
          letterSpacing: '0.01em',
          textTransform: 'capitalize',
          background: colors.bg,
          color: colors.text,
          lineHeight: '18px',
        }}
      >
        {status}
      </span>
    </div>
  )
}
