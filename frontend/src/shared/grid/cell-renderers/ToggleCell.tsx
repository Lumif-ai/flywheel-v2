import type { ICellRendererParams } from 'ag-grid-community'

export function ToggleCell(props: ICellRendererParams) {
  const { value } = props

  if (value == null) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const isTrue = Boolean(value)
  const dotColor = isTrue ? '#22C55E' : '#9CA3AF'
  const label = isTrue ? 'Yes' : 'No'

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          display: 'inline-block',
          width: '6px',
          height: '6px',
          borderRadius: '9999px',
          backgroundColor: dotColor,
          marginRight: '6px',
        }}
      />
      <span>{label}</span>
    </div>
  )
}
