import type { ICellRendererParams } from 'ag-grid-community'
import type { ContactListItem } from '../../types/pipeline'
import { NEXT_STEP_COLORS } from '../../constants'

const FOLLOW_UP_AMBER = { bg: '#FEF3C7', text: '#D97706' }

export function NextStepCell(props: ICellRendererParams<ContactListItem>) {
  const { value } = props
  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ color: '#9CA3AF' }}>&mdash;</span>
      </div>
    )
  }

  const label = String(value)
  let colors = NEXT_STEP_COLORS[label]
  if (!colors && label.startsWith('Follow up in')) {
    colors = FOLLOW_UP_AMBER
  }
  if (!colors) {
    colors = { bg: '#F3F4F6', text: '#6B7280' }
  }

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
          background: colors.bg,
          color: colors.text,
          whiteSpace: 'nowrap',
          lineHeight: '18px',
        }}
      >
        {label}
      </span>
    </div>
  )
}
