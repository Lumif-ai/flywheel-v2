import type { ICellRendererParams } from 'ag-grid-community'
import type { Lead } from '../../types/lead'

export function LeadCompanyCell(props: ICellRendererParams<Lead>) {
  const { data } = props
  if (!data) return null

  return (
    <div className="flex flex-col justify-center min-w-0 h-full">
      <span
        style={{
          fontWeight: 600,
          color: 'var(--heading-text)',
          fontSize: '14px',
          lineHeight: '1.3',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {data.name}
      </span>
      {data.domain && (
        <span
          style={{
            fontSize: '12px',
            color: 'var(--secondary-text)',
            lineHeight: '1.3',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.domain}
        </span>
      )}
    </div>
  )
}
