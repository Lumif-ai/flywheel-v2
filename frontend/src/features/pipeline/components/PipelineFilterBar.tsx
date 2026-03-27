import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { colors, typography } from '@/lib/design-tokens'

interface MultiSelectProps {
  label: string
  options: string[]
  selected: string[]
  onChange: (values: string[]) => void
}

function MultiSelect({ label, options, selected, onChange }: MultiSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const toggle = (val: string) => {
    onChange(
      selected.includes(val) ? selected.filter((v) => v !== val) : [...selected, val]
    )
  }

  const triggerLabel = selected.length > 0 ? `${label} (${selected.length})` : label

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          fontSize: typography.caption.size,
          padding: '6px 12px',
          borderRadius: '8px',
          border: `1px solid ${open ? 'var(--brand-coral)' : colors.subtleBorder}`,
          background: colors.cardBg,
          color: selected.length > 0 ? 'var(--brand-coral)' : colors.secondaryText,
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          fontWeight: selected.length > 0 ? 500 : 400,
          transition: 'border-color 150ms, color 150ms',
        }}
      >
        {triggerLabel}
      </button>
      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            zIndex: 20,
            background: 'var(--card-bg)',
            border: `1px solid ${colors.subtleBorder}`,
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
            minWidth: '160px',
            padding: '4px 0',
          }}
        >
          {options.map((opt) => (
            <label
              key={opt}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '7px 12px',
                cursor: 'pointer',
                fontSize: typography.caption.size,
                color: colors.headingText,
                background: selected.includes(opt) ? 'var(--brand-tint-warm)' : 'transparent',
                transition: 'background 100ms',
              }}
              onMouseEnter={(e) => {
                if (!selected.includes(opt)) {
                  ;(e.currentTarget as HTMLElement).style.background = 'var(--hover-bg, rgba(0,0,0,0.03))'
                }
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.background = selected.includes(opt)
                  ? 'var(--brand-tint-warm)'
                  : 'transparent'
              }}
            >
              <input
                type="checkbox"
                checked={selected.includes(opt)}
                onChange={() => toggle(opt)}
                style={{ accentColor: 'var(--brand-coral)', cursor: 'pointer' }}
              />
              {opt}
            </label>
          ))}
          {selected.length > 0 && (
            <div style={{ borderTop: `1px solid ${colors.subtleBorder}`, margin: '4px 0' }}>
              <button
                onClick={() => onChange([])}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '6px 12px',
                  textAlign: 'left',
                  fontSize: typography.caption.size,
                  color: 'var(--brand-coral)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export interface PipelineFilterBarProps {
  fitTier: string[]
  onFitTierChange: (values: string[]) => void
  outreachStatus: string[]
  onOutreachStatusChange: (values: string[]) => void
  search: string
  onSearchChange: (value: string) => void
}

const FIT_TIER_OPTIONS = ['Excellent', 'Strong', 'Good', 'Fair', 'Weak']
const OUTREACH_STATUS_OPTIONS = ['Sent', 'Opened', 'Replied', 'Bounced']

export function PipelineFilterBar({
  fitTier,
  onFitTierChange,
  outreachStatus,
  onOutreachStatusChange,
  search,
  onSearchChange,
}: PipelineFilterBarProps) {
  const [localSearch, setLocalSearch] = useState(search)

  // 300ms debounce on search
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [localSearch, onSearchChange])

  // Keep localSearch in sync if parent resets it
  useEffect(() => {
    setLocalSearch(search)
  }, [search])

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        flexWrap: 'wrap',
      }}
    >
      {/* Search input */}
      <div style={{ position: 'relative', flex: '1', maxWidth: '280px' }}>
        <Search
          style={{
            position: 'absolute',
            left: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '14px',
            height: '14px',
            color: colors.secondaryText,
            pointerEvents: 'none',
          }}
        />
        <input
          type="text"
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          placeholder="Search companies..."
          style={{
            width: '100%',
            paddingLeft: '32px',
            paddingRight: '10px',
            paddingTop: '6px',
            paddingBottom: '6px',
            fontSize: typography.caption.size,
            borderRadius: '8px',
            border: `1px solid ${colors.subtleBorder}`,
            background: colors.cardBg,
            color: colors.headingText,
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Fit Tier multi-select */}
      <MultiSelect
        label="All Tiers"
        options={FIT_TIER_OPTIONS}
        selected={fitTier}
        onChange={onFitTierChange}
      />

      {/* Outreach Status multi-select */}
      <MultiSelect
        label="All Statuses"
        options={OUTREACH_STATUS_OPTIONS}
        selected={outreachStatus}
        onChange={onOutreachStatusChange}
      />
    </div>
  )
}
