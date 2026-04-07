import { useState } from 'react'
import { Search, SlidersHorizontal, ArrowUpDown, LayoutGrid, Kanban, Bookmark } from 'lucide-react'
import { SaveViewDialog } from './SaveViewDialog'
import type { SavedView } from '../types/pipeline'

export interface PipelineToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  onToggleFilters: () => void
  filtersVisible: boolean
  showRetired: boolean
  onShowRetiredChange: (value: boolean) => void
  /** Current active filters — needed for save view */
  filters?: SavedView['filters']
  /** Current sort — passed to save view */
  sort?: SavedView['sort']
}

const BTN_STYLE: React.CSSProperties = {
  height: '32px',
  borderRadius: '6px',
  border: '1px solid #E5E7EB',
  background: '#FFFFFF',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '0 8px',
  transition: 'background 150ms',
}

export function PipelineToolbar({
  search,
  onSearchChange,
  onToggleFilters,
  filtersVisible,
  showRetired,
  onShowRetiredChange,
  filters,
  sort,
}: PipelineToolbarProps) {
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)

  // Show save button when at least one filter is active
  const hasActiveFilters = !!(
    filters &&
    (
      (filters.stage && filters.stage.length > 0) ||
      (filters.fitTier && filters.fitTier.length > 0) ||
      (filters.relationshipType && filters.relationshipType.length > 0) ||
      filters.source ||
      (filters.view && filters.view !== 'all') ||
      filters.search
    )
  )

  return (
    <>
      <div
        className="flex items-center justify-between gap-3"
        style={{ padding: '6px 0', marginBottom: '4px' }}
      >
        {/* Left: Search */}
        <div style={{ position: 'relative', width: '280px' }}>
          <Search
            style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '14px',
              height: '14px',
              color: '#9CA3AF',
              pointerEvents: 'none',
            }}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search pipeline..."
            style={{
              width: '100%',
              height: '32px',
              border: '1px solid #E5E7EB',
              borderRadius: '8px',
              padding: '6px 10px 6px 32px',
              fontSize: '13px',
              color: '#121212',
              background: '#FFFFFF',
              outline: 'none',
            }}
          />
        </div>

        {/* Right: buttons */}
        <div className="flex items-center gap-2">
          {/* Save view button */}
          {hasActiveFilters && (
            <button
              onClick={() => setSaveDialogOpen(true)}
              style={{
                ...BTN_STYLE,
                gap: '4px',
                padding: '0 10px',
                color: '#6B7280',
                fontSize: '13px',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#F3F4F6' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#FFFFFF' }}
              title="Save current view"
            >
              <Bookmark style={{ width: '14px', height: '14px' }} />
              <span>Save view</span>
            </button>
          )}

          {/* Show retired toggle */}
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#6B7280', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showRetired}
              onChange={(e) => onShowRetiredChange(e.target.checked)}
              style={{ accentColor: '#E94D35' }}
            />
            Show retired
          </label>

          {/* Filter toggle */}
          <button
            onClick={onToggleFilters}
            style={{
              ...BTN_STYLE,
              background: filtersVisible ? 'rgba(233,77,53,0.08)' : '#FFFFFF',
              borderColor: filtersVisible ? '#E94D35' : '#E5E7EB',
              color: filtersVisible ? '#E94D35' : '#6B7280',
            }}
            onMouseEnter={(e) => {
              if (!filtersVisible) e.currentTarget.style.background = '#F3F4F6'
            }}
            onMouseLeave={(e) => {
              if (!filtersVisible) e.currentTarget.style.background = '#FFFFFF'
            }}
            title="Toggle filters"
          >
            <SlidersHorizontal style={{ width: '14px', height: '14px' }} />
          </button>

          {/* Sort (placeholder) */}
          <button
            style={{ ...BTN_STYLE, color: '#6B7280' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#F3F4F6' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#FFFFFF' }}
            title="Sort (use column headers)"
          >
            <ArrowUpDown style={{ width: '14px', height: '14px' }} />
          </button>

          {/* Grid / Board toggle */}
          <div className="flex items-center" style={{ border: '1px solid #E5E7EB', borderRadius: '6px', overflow: 'hidden' }}>
            <button
              style={{
                height: '30px',
                padding: '0 8px',
                background: '#FFFFFF',
                border: 'none',
                borderRight: '1px solid #E5E7EB',
                cursor: 'default',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#E94D35',
              }}
              title="Grid view (active)"
            >
              <LayoutGrid style={{ width: '14px', height: '14px' }} />
            </button>
            <button
              disabled
              style={{
                height: '30px',
                padding: '0 8px',
                background: '#FAFAFA',
                border: 'none',
                cursor: 'not-allowed',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#D1D5DB',
                opacity: 0.6,
              }}
              title="Board view coming soon"
            >
              <Kanban style={{ width: '14px', height: '14px' }} />
            </button>
          </div>
        </div>
      </div>

      {/* Save View Dialog */}
      {filters && (
        <SaveViewDialog
          open={saveDialogOpen}
          onOpenChange={setSaveDialogOpen}
          filters={filters}
          sort={sort}
        />
      )}
    </>
  )
}
