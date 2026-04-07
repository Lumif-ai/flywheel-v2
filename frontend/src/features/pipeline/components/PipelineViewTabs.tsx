import type { ViewTab } from '../types/pipeline'

export type { ViewTab }

export type PipelineView = ViewTab

export interface PipelineViewTabsProps {
  activeView: ViewTab
  onViewChange: (view: ViewTab) => void
}

const TABS: { id: ViewTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'needs_action', label: 'Needs Action' },
  { id: 'replied', label: 'Replied' },
  { id: 'stale', label: 'Stale' },
]

export function PipelineViewTabs({ activeView, onViewChange }: PipelineViewTabsProps) {
  return (
    <div className="flex items-center gap-0.5">
      {TABS.map(({ id, label }) => {
        const isActive = activeView === id
        return (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            style={{
              padding: '4px 10px',
              fontSize: '13px',
              fontWeight: 500,
              color: isActive ? '#121212' : '#9CA3AF',
              background: 'transparent',
              border: 'none',
              borderBottom: isActive ? '2px solid #E94D35' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'color 150ms, border-color 150ms',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.color = '#6B7280'
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.color = '#9CA3AF'
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
