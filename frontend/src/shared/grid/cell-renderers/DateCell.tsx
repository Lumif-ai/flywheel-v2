import type { ICellRendererParams } from 'ag-grid-community'
import { formatDistanceToNow, format, differenceInDays } from 'date-fns'

export function DateCell(props: ICellRendererParams) {
  const { value } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '12px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const date = new Date(value as string)
  const daysDiff = Math.abs(differenceInDays(new Date(), date))

  const display =
    daysDiff <= 30
      ? formatDistanceToNow(date, { addSuffix: true })
      : format(date, 'MMM d')

  return (
    <div className="flex items-center h-full">
      <span style={{ fontSize: '12px', color: '#6B7280' }}>{display}</span>
    </div>
  )
}
