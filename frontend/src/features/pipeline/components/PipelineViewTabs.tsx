import { useSearchParams } from 'react-router'
import { colors, typography } from '@/lib/design-tokens'

export type PipelineView = 'all' | 'hot' | 'stale' | 'replied'

export interface PipelineViewTabsProps {
  activeView: PipelineView
  onViewChange: (view: PipelineView) => void
  counts?: {
    all: number
    hot: number
    stale: number
    replied: number
  }
}

const TABS: { key: PipelineView; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'hot', label: 'Hot' },
  { key: 'stale', label: 'Stale' },
  { key: 'replied', label: 'Replied' },
]

export function PipelineViewTabs({ activeView, onViewChange, counts }: PipelineViewTabsProps) {
  const [, setSearchParams] = useSearchParams()

  const handleTabClick = (view: PipelineView) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (view === 'all') {
        next.delete('view')
      } else {
        next.set('view', view)
      }
      return next
    })
    onViewChange(view)
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        borderBottom: `1px solid ${colors.subtleBorder}`,
        marginBottom: '16px',
      }}
    >
      {TABS.map(({ key, label }) => {
        const isActive = activeView === key
        const count = counts?.[key]
        return (
          <button
            key={key}
            onClick={() => handleTabClick(key)}
            style={{
              padding: '8px 14px',
              fontSize: typography.caption.size,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--brand-coral)' : colors.secondaryText,
              background: 'none',
              border: 'none',
              borderBottom: isActive
                ? '2px solid var(--brand-coral)'
                : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: '-1px',
              transition: 'color 150ms, border-color 150ms',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
            {count !== undefined && count > 0 && (
              <span
                style={{
                  marginLeft: '6px',
                  fontSize: '11px',
                  color: isActive ? 'var(--brand-coral)' : colors.secondaryText,
                  opacity: 0.8,
                }}
              >
                {count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
