import type { ICellRendererParams } from 'ag-grid-community'
import { STAGE_COLORS } from '../../types/lead'
import type { Lead } from '../../types/lead'

export function StageBadge(props: ICellRendererParams<Lead>) {
  const { data } = props
  if (!data) return null

  const stage = data.pipeline_stage
  if (!stage) return null

  const color = STAGE_COLORS[stage.toLowerCase()] ?? '#6b7280'

  return (
    <div className="flex items-center h-full">
      <span
        aria-label={`${stage} stage`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          fontSize: '12px',
          fontWeight: 500,
          color,
          textTransform: 'capitalize',
        }}
      >
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        {stage}
      </span>
    </div>
  )
}
