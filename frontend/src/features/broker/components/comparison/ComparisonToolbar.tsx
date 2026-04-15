import { Download, Monitor, FileText } from 'lucide-react'

interface ComparisonToolbarProps {
  showDifferencesOnly: boolean
  onToggleDifferences: () => void
  highlightBest: boolean
  onToggleHighlight: () => void
  onExport: () => void
  isExporting: boolean
  viewMode: 'interactive' | 'pdf'
  onViewModeChange: (mode: 'interactive' | 'pdf') => void
}

function Toggle({
  checked,
  onToggle,
  label,
}: {
  checked: boolean
  onToggle: () => void
  label: string
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onToggle}
        className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors"
        style={{ backgroundColor: checked ? '#E94D35' : '#E5E7EB' }}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform ${
            checked ? 'translate-x-5' : 'translate-x-0.5'
          } mt-0.5`}
        />
      </button>
      <span className="text-sm text-gray-700">{label}</span>
    </div>
  )
}

function ViewModeToggle({
  viewMode,
  onViewModeChange,
}: {
  viewMode: 'interactive' | 'pdf'
  onViewModeChange: (mode: 'interactive' | 'pdf') => void
}) {
  return (
    <div className="flex items-center rounded-lg border border-gray-200 overflow-hidden">
      <button
        type="button"
        onClick={() => onViewModeChange('interactive')}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors ${
          viewMode === 'interactive'
            ? 'bg-gray-900 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        <Monitor className="h-3.5 w-3.5" />
        Interactive
      </button>
      <button
        type="button"
        onClick={() => onViewModeChange('pdf')}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors ${
          viewMode === 'pdf'
            ? 'bg-gray-900 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        <FileText className="h-3.5 w-3.5" />
        PDF
      </button>
    </div>
  )
}

export function ComparisonToolbar({
  showDifferencesOnly,
  onToggleDifferences,
  highlightBest,
  onToggleHighlight,
  onExport,
  isExporting,
  viewMode,
  onViewModeChange,
}: ComparisonToolbarProps) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-6">
        <Toggle
          checked={showDifferencesOnly}
          onToggle={onToggleDifferences}
          label="Show differences only"
        />
        <Toggle
          checked={highlightBest}
          onToggle={onToggleHighlight}
          label="Highlight best values"
        />
      </div>
      <div className="flex items-center gap-3">
        <ViewModeToggle viewMode={viewMode} onViewModeChange={onViewModeChange} />
        {viewMode === 'interactive' && (
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="h-4 w-4" />
            {isExporting ? 'Exporting...' : 'Export Excel'}
          </button>
        )}
        {viewMode === 'pdf' && (
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-700 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
          >
            <FileText className="h-4 w-4" />
            Print
          </button>
        )}
      </div>
    </div>
  )
}
