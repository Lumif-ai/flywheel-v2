import type { ICellRendererParams } from 'ag-grid-community'
import { typography } from '@/lib/design-tokens'
import type { PipelineItem } from '../../types/pipeline'

export function ContactCell(props: ICellRendererParams<PipelineItem>) {
  const { data } = props
  if (!data) return null

  if (!data.primary_contact_name) {
    return (
      <span style={{ color: 'var(--secondary-text)', fontSize: typography.body.size }}>
        &mdash;
      </span>
    )
  }

  return (
    <div className="flex flex-col justify-center h-full">
      <span
        style={{
          fontSize: typography.body.size,
          color: 'var(--body-text)',
          lineHeight: '1.3',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {data.primary_contact_name}
      </span>
      {data.primary_contact_title && (
        <span
          style={{
            fontSize: typography.caption.size,
            color: 'var(--secondary-text)',
            lineHeight: '1.3',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.primary_contact_title}
        </span>
      )}
    </div>
  )
}
