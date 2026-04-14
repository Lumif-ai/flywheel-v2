interface ComparisonToolbarProps {
  showDifferencesOnly: boolean
  onToggleDifferences: () => void
  highlightBest: boolean
  onToggleHighlight: () => void
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
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors ${
          checked ? 'bg-blue-600' : 'bg-gray-200'
        }`}
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

export function ComparisonToolbar({
  showDifferencesOnly,
  onToggleDifferences,
  highlightBest,
  onToggleHighlight,
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
      {/* Right side reserved for export button (Plan 03) */}
    </div>
  )
}
