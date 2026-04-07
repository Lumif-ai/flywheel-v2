import { List, LayoutGrid } from 'lucide-react'
import { cn } from '@/lib/cn'

type ViewMode = 'list' | 'grid'

interface ViewToggleProps {
  view: ViewMode
  onViewChange: (view: ViewMode) => void
  className?: string
}

export function ViewToggle({ view, onViewChange, className }: ViewToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="View mode"
      className={cn(
        'inline-flex items-center rounded-lg border border-[var(--subtle-border)] p-0.5 gap-0.5',
        className,
      )}
    >
      <button
        type="button"
        role="radio"
        aria-checked={view === 'list'}
        aria-label="List view"
        onClick={() => onViewChange('list')}
        className={cn(
          'inline-flex items-center justify-center size-8 rounded-md transition-all duration-200',
          view === 'list'
            ? 'bg-[var(--brand-coral)] text-white shadow-sm'
            : 'text-[var(--secondary-text)] hover:bg-[var(--brand-tint)] hover:text-[var(--heading-text)]',
        )}
      >
        <List size={16} />
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={view === 'grid'}
        aria-label="Grid view"
        onClick={() => onViewChange('grid')}
        className={cn(
          'inline-flex items-center justify-center size-8 rounded-md transition-all duration-200',
          view === 'grid'
            ? 'bg-[var(--brand-coral)] text-white shadow-sm'
            : 'text-[var(--secondary-text)] hover:bg-[var(--brand-tint)] hover:text-[var(--heading-text)]',
        )}
      >
        <LayoutGrid size={16} />
      </button>
    </div>
  )
}

export type { ViewMode }
