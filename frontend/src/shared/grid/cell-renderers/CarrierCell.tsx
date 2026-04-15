import type { ICellRendererParams } from 'ag-grid-community'
import { getCarrierColor, getInitials } from '@/features/broker/utils/carrierColorUtils'
import { CarrierLogoByName } from '@/features/broker/components/carrier-logos'

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
  const logo = CarrierLogoByName({ name, size: 24 })

  return (
    <div className="flex items-center h-full" style={{ gap: '8px' }}>
      {logo || <InitialsCircle name={name} />}
      <span>{name}</span>
    </div>
  )
}

/** Fallback colored circle with initials when no SVG logo is available */
function InitialsCircle({ name }: { name: string }) {
  const bg = getCarrierColor(name)

  return (
    <span
      style={{
        width: '24px',
        height: '24px',
        borderRadius: '6px',
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
  )
}
