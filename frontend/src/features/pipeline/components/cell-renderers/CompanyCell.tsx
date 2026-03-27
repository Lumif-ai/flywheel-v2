import type { ICellRendererParams } from 'ag-grid-community'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { typography } from '@/lib/design-tokens'
import type { PipelineItem } from '../../types/pipeline'

export function CompanyCell(props: ICellRendererParams<PipelineItem>) {
  const { data } = props
  if (!data) return null

  const initials = data.name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')

  return (
    <div className="flex items-center gap-2.5 h-full">
      <Avatar size="default">
        <AvatarFallback
          style={{
            background: 'var(--brand-light)',
            color: 'var(--brand-coral)',
            fontWeight: '600',
            fontSize: '13px',
          }}
        >
          {initials}
        </AvatarFallback>
      </Avatar>
      <div className="flex flex-col justify-center min-w-0">
        <span
          style={{
            fontWeight: '500',
            color: 'var(--heading-text)',
            fontSize: typography.body.size,
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
              fontSize: typography.caption.size,
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
    </div>
  )
}
