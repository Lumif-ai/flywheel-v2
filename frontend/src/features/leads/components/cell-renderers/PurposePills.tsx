import type { ICellRendererParams } from 'ag-grid-community'
import type { Lead } from '../../types/lead'

const MAX_VISIBLE = 2

export function PurposePills(props: ICellRendererParams<Lead>) {
  const { data } = props
  if (!data) return null

  const purposes = data.purpose
  if (!purposes || purposes.length === 0) return null

  const visible = purposes.slice(0, MAX_VISIBLE)
  const overflow = purposes.length - MAX_VISIBLE

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          fontSize: '12px',
          fontWeight: 400,
          color: '#6b7280',
          whiteSpace: 'nowrap',
        }}
      >
        {visible.join(', ')}
      </span>
      {overflow > 0 && (
        <span style={{ fontSize: '11px', color: '#9CA3AF', marginLeft: '2px' }}>
          +{overflow}
        </span>
      )}
    </div>
  )
}
