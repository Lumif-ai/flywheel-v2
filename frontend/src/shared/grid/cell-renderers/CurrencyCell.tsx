import type { ICellRendererParams } from 'ag-grid-community'

interface CurrencyCellParams {
  currency?: string
}

export function CurrencyCell(props: ICellRendererParams & CurrencyCellParams) {
  const { value, currency } = props

  if (value == null) {
    return (
      <div className="flex items-center justify-end h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(value))

  return (
    <div className="flex items-center justify-end h-full">
      <span style={{ fontFeatureSettings: '"tnum"' }}>{formatted}</span>
    </div>
  )
}
