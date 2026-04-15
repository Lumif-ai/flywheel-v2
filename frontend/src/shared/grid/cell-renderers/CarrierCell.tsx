import type { ICellRendererParams } from 'ag-grid-community'

const PALETTE = ['#E94D35', '#3B82F6', '#22C55E', '#F97316', '#A855F7', '#14B8A6', '#6366F1']

function hashCode(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash)
}

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
  const dotColor = PALETTE[hashCode(name) % PALETTE.length]

  return (
    <div className="flex items-center h-full" style={{ gap: '8px' }}>
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '9999px',
          backgroundColor: dotColor,
          flexShrink: 0,
        }}
      />
      <span>{name}</span>
    </div>
  )
}
