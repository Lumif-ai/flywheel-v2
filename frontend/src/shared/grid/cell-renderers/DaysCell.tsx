import type { ICellRendererParams } from 'ag-grid-community'

export function DaysCell(props: ICellRendererParams) {
  const { value } = props

  if (value == null) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const n = Number(value)

  if (n === 0) {
    return (
      <div className="flex items-center h-full">
        <span>Today</span>
      </div>
    )
  }

  const isOverdue = n < 0
  const abs = Math.abs(n)
  const unit = abs === 1 ? 'day' : 'days'
  const text = isOverdue ? `${abs} ${unit} ago` : `${abs} ${unit}`

  return (
    <div className="flex items-center h-full">
      <span style={isOverdue ? { color: '#EF4444' } : undefined}>{text}</span>
    </div>
  )
}
