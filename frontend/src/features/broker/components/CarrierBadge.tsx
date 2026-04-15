import { getCarrierColor, getInitials } from '@/features/broker/utils/carrierColorUtils'
import { CarrierLogoByName } from './carrier-logos'

interface CarrierBadgeProps {
  name: string
  size?: number       // circle diameter in px, default 24
  showName?: boolean  // render name text beside circle, default true
  className?: string
}

export function CarrierBadge({ name, size = 24, showName = true, className }: CarrierBadgeProps) {
  const logo = CarrierLogoByName({ name, size })

  return (
    <div className={`flex items-center${className ? ` ${className}` : ''}`} style={{ gap: '6px' }}>
      {logo || <InitialsCircle name={name} size={size} />}
      {showName && <span>{name}</span>}
    </div>
  )
}

/** Fallback colored circle with initials when no SVG logo is available */
function InitialsCircle({ name, size }: { name: string; size: number }) {
  const bg = getCarrierColor(name)
  const fontSize = Math.max(9, Math.round(size * 0.38))

  return (
    <span
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: '6px',
        backgroundColor: bg,
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: `${fontSize}px`,
        fontWeight: 600,
        flexShrink: 0,
        letterSpacing: '0.02em',
      }}
    >
      {getInitials(name)}
    </span>
  )
}
