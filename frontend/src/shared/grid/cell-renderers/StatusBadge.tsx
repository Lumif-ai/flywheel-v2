import type { ICellRendererParams } from 'ag-grid-community'

export interface StatusBadgeColors {
  [key: string]: { bg: string; text: string }
}

interface StatusBadgeParams {
  colorMap: StatusBadgeColors
}

const DEFAULT_COLORS = { bg: '#F3F4F6', text: '#6B7280' }

export function StatusBadge(props: ICellRendererParams & StatusBadgeParams) {
  const { value, colorMap } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const label = String(value)
  const key = label.toLowerCase()
  const colors = colorMap?.[key] ?? DEFAULT_COLORS

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-block',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 600,
          background: colors.bg,
          color: colors.text,
        }}
      >
        {label}
      </span>
    </div>
  )
}
