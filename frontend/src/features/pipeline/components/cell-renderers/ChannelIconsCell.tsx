import type { ICellRendererParams } from 'ag-grid-community'
import type { ContactListItem } from '../../types/pipeline'
import { Mail, Linkedin, Phone } from 'lucide-react'

const CHANNEL_ICONS: Record<string, { icon: typeof Mail; label: string }> = {
  email: { icon: Mail, label: 'Email' },
  linkedin: { icon: Linkedin, label: 'LinkedIn' },
  phone: { icon: Phone, label: 'Phone' },
}

export function ChannelIconsCell(props: ICellRendererParams<ContactListItem>) {
  const channels = (props.value as string[]) ?? []
  if (channels.length === 0) {
    return (
      <div className="flex items-center h-full">
        <span style={{ color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 h-full">
      {channels.map((ch) => {
        const cfg = CHANNEL_ICONS[ch]
        if (!cfg) return null
        const Icon = cfg.icon
        return (
          <span
            key={ch}
            title={cfg.label}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '22px',
              height: '22px',
              borderRadius: '4px',
              background: '#F9FAFB',
              border: '1px solid #F3F4F6',
            }}
          >
            <Icon style={{ width: '13px', height: '13px', color: '#6B7280' }} />
          </span>
        )
      })}
    </div>
  )
}
