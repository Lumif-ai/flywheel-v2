import type { ICellRendererParams } from 'ag-grid-community'
import { getCarrierColor, getInitials } from '@/features/broker/utils/carrierColorUtils'

export function CarrierCell(props: ICellRendererParams) {
  const { value } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const name = String(value)
  const bg = getCarrierColor(name)

  return (
    <div className="flex items-center h-full" style={{ gap: '8px' }}>
      <span
        style={{
          width: '28px',
          height: '28px',
          borderRadius: '9999px',
          backgroundColor: bg,
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '10px',
          fontWeight: 600,
          flexShrink: 0,
          letterSpacing: '0.02em',
        }}
      >
        {getInitials(name)}
      </span>
      <span>{name}</span>
    </div>
  )
}
