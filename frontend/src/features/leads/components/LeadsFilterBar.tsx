import { useEffect, useRef, useState } from 'react'
import { Search, X, ChevronDown, Check } from 'lucide-react'
import { STAGE_ORDER } from '../types/lead'

/* ─── Types ───────────────────────────────────────────────────── */

interface LeadsFilterBarProps {
  search: string
  onSearchChange: (s: string) => void
  activeStage: string | null
  onStageChange: (s: string | null) => void
  fitTier: string | null
  onFitTierChange: (s: string | null) => void
  purpose: string | null
  onPurposeChange: (s: string | null) => void
}

type DropdownId = 'stage' | 'fit' | 'purpose' | null

const FIT_TIER_OPTIONS = ['Strong', 'Good', 'Moderate', 'Weak', 'No Fit']
const PURPOSE_OPTIONS = ['sales', 'fundraising', 'advisors', 'partnerships']

/* ─── Single-select dropdown ──────────────────────────────────── */

interface SingleSelectProps {
  id: DropdownId
  label: string
  options: string[]
  selected: string | null
  onChange: (value: string | null) => void
  openDropdown: DropdownId
  setOpenDropdown: (id: DropdownId) => void
}

function SingleSelectDropdown({
  id,
  label,
  options,
  selected,
  onChange,
  openDropdown,
  setOpenDropdown,
}: SingleSelectProps) {
  const ref = useRef<HTMLDivElement>(null)
  const isOpen = openDropdown === id
  const hasActive = selected !== null

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpenDropdown(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [isOpen, setOpenDropdown])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenDropdown(null)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, setOpenDropdown])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpenDropdown(isOpen ? null : id)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className="inline-flex items-center gap-1.5 rounded-lg transition-colors"
        style={{
          padding: '6px 12px',
          fontSize: '13px',
          fontWeight: 500,
          background: hasActive ? 'var(--brand-tint)' : 'transparent',
          color: hasActive ? 'var(--brand-coral)' : 'var(--secondary-text)',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        {label}
        <ChevronDown
          style={{
            width: '14px',
            height: '14px',
            transition: 'transform 200ms ease',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {isOpen && (
        <div
          role="listbox"
          className="absolute top-full left-0 mt-1 z-50 rounded-xl border bg-white overflow-auto"
          style={{
            boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
            borderColor: '#E5E7EB',
            minWidth: '160px',
            maxHeight: '240px',
            padding: '4px 0',
          }}
        >
          {/* "All" option to clear */}
          <button
            role="option"
            aria-selected={selected === null}
            onClick={() => {
              onChange(null)
              setOpenDropdown(null)
            }}
            className="flex items-center gap-2 w-full text-left transition-colors"
            style={{
              padding: '8px 12px',
              fontSize: '13px',
              fontWeight: selected === null ? 500 : 400,
              color: selected === null ? 'var(--brand-coral)' : '#121212',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(0,0,0,0.04)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'none'
            }}
          >
            <span style={{ width: '16px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
              {selected === null && <Check style={{ width: '14px', height: '14px' }} />}
            </span>
            All
          </button>

          {options.map((opt) => {
            const isSelected = selected === opt
            return (
              <button
                key={opt}
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(isSelected ? null : opt)
                  setOpenDropdown(null)
                }}
                className="flex items-center gap-2 w-full text-left transition-colors"
                style={{
                  padding: '8px 12px',
                  fontSize: '13px',
                  fontWeight: isSelected ? 500 : 400,
                  color: isSelected ? 'var(--brand-coral)' : '#121212',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  textTransform: id === 'purpose' ? 'capitalize' : undefined,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(0,0,0,0.04)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'none'
                }}
              >
                <span style={{ width: '16px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  {isSelected && <Check style={{ width: '14px', height: '14px' }} />}
                </span>
                {opt}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ─── Main filter bar ─────────────────────────────────────────── */

export function LeadsFilterBar({
  search,
  onSearchChange,
  activeStage,
  onStageChange,
  fitTier,
  onFitTierChange,
  purpose,
  onPurposeChange,
}: LeadsFilterBarProps) {
  const [openDropdown, setOpenDropdown] = useState<DropdownId>(null)

  // Build active filter chips
  const chips: { label: string; remove: () => void }[] = []
  if (activeStage) chips.push({ label: activeStage, remove: () => onStageChange(null) })
  if (fitTier) chips.push({ label: fitTier, remove: () => onFitTierChange(null) })
  if (purpose) chips.push({ label: purpose, remove: () => onPurposeChange(null) })

  return (
    <div
      className="flex items-center gap-3 flex-wrap"
      role="search"
      aria-label="Search leads"
    >
      {/* Search input */}
      <div
        className="flex items-center gap-2 flex-1 min-w-0"
        style={{
          maxWidth: '384px',
          height: '40px',
          borderRadius: '12px',
          border: '1px solid var(--subtle-border)',
          padding: '0 12px',
          transition: 'border-color 200ms ease, box-shadow 200ms ease',
        }}
        onFocus={(e) => {
          const container = e.currentTarget
          container.style.borderColor = 'var(--brand-coral)'
          container.style.boxShadow = '0 0 0 2px rgba(233,77,53,0.15)'
        }}
        onBlur={(e) => {
          const container = e.currentTarget
          if (!container.contains(e.relatedTarget as Node)) {
            container.style.borderColor = 'var(--subtle-border)'
            container.style.boxShadow = 'none'
          }
        }}
      >
        <Search style={{ width: '16px', height: '16px', color: 'var(--secondary-text)', flexShrink: 0 }} />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search leads..."
          className="flex-1 bg-transparent outline-none placeholder:text-[#D1D5DB]"
          style={{ color: 'var(--heading-text)', fontSize: '13px', minWidth: 0, border: 'none' }}
        />
        {search && (
          <button
            onClick={() => onSearchChange('')}
            className="p-0.5 rounded hover:bg-[#F3F4F6] transition-colors"
            style={{ background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0 }}
            aria-label="Clear search"
          >
            <X style={{ width: '14px', height: '14px', color: 'var(--secondary-text)' }} />
          </button>
        )}
      </div>

      {/* Divider */}
      <div style={{ width: '1px', height: '24px', background: 'var(--subtle-border)' }} />

      {/* Dropdowns */}
      <SingleSelectDropdown
        id="stage"
        label="Stage"
        options={STAGE_ORDER}
        selected={activeStage}
        onChange={onStageChange}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
      />
      <SingleSelectDropdown
        id="fit"
        label="Fit Tier"
        options={FIT_TIER_OPTIONS}
        selected={fitTier}
        onChange={onFitTierChange}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
      />
      <SingleSelectDropdown
        id="purpose"
        label="Purpose"
        options={PURPOSE_OPTIONS}
        selected={purpose}
        onChange={onPurposeChange}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
      />

      {/* Active filter chips */}
      {chips.map((chip) => (
        <button
          key={chip.label}
          onClick={chip.remove}
          className="inline-flex items-center gap-1 rounded-full"
          style={{
            padding: '4px 10px',
            background: 'var(--brand-tint)',
            color: 'var(--brand-coral)',
            fontSize: '12px',
            fontWeight: 500,
            border: 'none',
            cursor: 'pointer',
            textTransform: 'capitalize',
          }}
        >
          {chip.label}
          <X style={{ width: '12px', height: '12px' }} />
        </button>
      ))}
    </div>
  )
}
