import { ExternalLink } from 'lucide-react'
import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineListItem } from '../../types/pipeline'

export function NameCell(props: ICellRendererParams<PipelineListItem>) {
  const { data } = props
  if (!data) return null

  const isCompany = data.entity_type === 'company'
  const initial = (data.name?.[0] ?? '?').toUpperCase()

  return (
    <div className="flex items-center h-full" style={{ gap: '8px' }}>
      {/* Avatar */}
      <div
        style={{
          width: '28px',
          height: '28px',
          minWidth: '28px',
          borderRadius: isCompany ? '6px' : '50%',
          background: '#F3F4F6',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          fontWeight: 600,
          color: '#6B7280',
        }}
      >
        {initial}
      </div>

      {/* Name + domain icon inline */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          minWidth: 0,
          gap: '4px',
        }}
      >
        <span
          style={{
            fontSize: '13px',
            fontWeight: 600,
            color: '#121212',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.name}
        </span>
        {isCompany && data.domain && (
          <a
            href={`https://${data.domain}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ color: '#9CA3AF', display: 'inline-flex', flexShrink: 0 }}
            title={data.domain}
          >
            <ExternalLink size={12} />
          </a>
        )}
      </div>
    </div>
  )
}
