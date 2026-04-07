import type { ICellRendererParams } from 'ag-grid-community'
import { Mail, Linkedin, Phone, Globe, MessageSquare } from 'lucide-react'
import type { PipelineListItem } from '../../types/pipeline'

const CHANNEL_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  linkedin: Linkedin,
  phone: Phone,
  web: Globe,
  chat: MessageSquare,
}

export function ChannelsCell(props: ICellRendererParams<PipelineListItem>) {
  const { value } = props
  const channels = value as string[] | null | undefined

  if (!channels || channels.length === 0) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '12px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const visible = channels.slice(0, 3)
  const extra = channels.length - 3

  return (
    <div className="flex items-center h-full" style={{ gap: '4px' }}>
      {visible.map((ch) => {
        const Icon = CHANNEL_ICONS[ch.toLowerCase()] ?? Globe
        return <Icon key={ch} style={{ width: '14px', height: '14px', color: '#6B7280' }} />
      })}
      {extra > 0 && (
        <span style={{ fontSize: '10px', fontWeight: 600, color: '#9CA3AF' }}>
          +{extra}
        </span>
      )}
    </div>
  )
}
