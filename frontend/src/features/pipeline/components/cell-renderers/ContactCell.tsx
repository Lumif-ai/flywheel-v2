import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

export function ContactCell(props: ICellRendererParams<PipelineListItem>) {
  const { data } = props
  if (!data) return null

  const contact = data.primary_contact

  if (contact?.name) {
    return (
      <div className="flex flex-col justify-center h-full" style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: '13px',
            color: '#121212',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {contact.name}
        </div>
        {contact.title && (
          <div
            style={{
              fontSize: '11px',
              color: '#9CA3AF',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {contact.title}
          </div>
        )}
      </div>
    )
  }

  if (data.contact_count > 0) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
          {data.contact_count} contacts
        </span>
      </div>
    )
  }

  return (
    <div className="flex items-center h-full">
      <span style={{ fontSize: '12px', color: '#D1D5DB' }}>&mdash;</span>
    </div>
  )
}
