import { getCarrierColor, getInitials } from '@/features/broker/utils/carrierColorUtils'

interface CarrierBadgeProps {
  name: string
  size?: number       // circle diameter in px, default 24
  showName?: boolean  // render name text beside circle, default true
  className?: string
}

export function CarrierBadge({ name, size = 24, showName = true, className }: CarrierBadgeProps) {
  const bg = getCarrierColor(name)
  const fontSize = Math.max(9, Math.round(size * 0.38))

  return (
    <div className={`flex items-center${className ? ` ${className}` : ''}`} style={{ gap: '6px' }}>
      <span
        style={{
          width: `${size}px`,
          height: `${size}px`,
          borderRadius: '9999px',
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
      {showName && <span>{name}</span>}
    </div>
  )
}
