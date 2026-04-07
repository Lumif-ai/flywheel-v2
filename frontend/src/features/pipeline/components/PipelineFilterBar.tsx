import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

/* ------------------------------------------------------------------ */
/* Multi-select dropdown                                               */
/* ------------------------------------------------------------------ */

interface MultiSelectProps {
  label: string
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (values: string[]) => void
}

function MultiSelectFilter({ label, options, selected, onChange }: MultiSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (val: string) => {
    onChange(selected.includes(val) ? selected.filter((v) => v !== val) : [...selected, val])
  }

  const hasActive = selected.length > 0

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 10px',
          borderRadius: '6px',
          border: hasActive ? '1px solid #E94D35' : '1px solid #E5E7EB',
          background: hasActive ? '#FEF2F0' : '#FFFFFF',
          color: hasActive ? '#E94D35' : '#6B7280',
          fontSize: '12px',
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'all 150ms',
        }}
      >
        {label}
        {hasActive && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '16px',
              height: '16px',
              borderRadius: '9999px',
              background: 'rgba(233,77,53,0.12)',
              color: '#E94D35',
              fontSize: '10px',
              fontWeight: 700,
            }}
          >
            {selected.length}
          </span>
        )}
        <ChevronDown style={{ width: '12px', height: '12px' }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            zIndex: 20,
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: '8px',
            padding: '4px 0',
            boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
            minWidth: '160px',
          }}
        >
          {options.map((opt) => {
            const active = selected.includes(opt.value)
            return (
              <button
                key={opt.value}
                onClick={() => toggle(opt.value)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '6px 12px',
                  textAlign: 'left',
                  fontSize: '12px',
                  color: active ? '#E94D35' : '#121212',
                  fontWeight: active ? 500 : 400,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'background 100ms',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#FAFAFA' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              >
                <span
                  style={{
                    width: '14px',
                    height: '14px',
                    borderRadius: '3px',
                    border: active ? '2px solid #E94D35' : '1.5px solid #D1D5DB',
                    background: active ? 'rgba(233,77,53,0.1)' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {active && (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1 4L3 6L7 2" stroke="#E94D35" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </span>
                {opt.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Single-select dropdown                                              */
/* ------------------------------------------------------------------ */

interface SingleSelectProps {
  label: string
  options: { value: string; label: string }[]
  selected: string
  onChange: (value: string) => void
}

function SingleSelectFilter({ label, options, selected, onChange }: SingleSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const hasActive = selected !== ''

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 10px',
          borderRadius: '6px',
          border: hasActive ? '1px solid #E94D35' : '1px solid #E5E7EB',
          background: hasActive ? '#FEF2F0' : '#FFFFFF',
          color: hasActive ? '#E94D35' : '#6B7280',
          fontSize: '12px',
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'all 150ms',
        }}
      >
        {label}
        {hasActive && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '16px',
              height: '16px',
              borderRadius: '9999px',
              background: 'rgba(233,77,53,0.12)',
              color: '#E94D35',
              fontSize: '10px',
              fontWeight: 700,
            }}
          >
            1
          </span>
        )}
        <ChevronDown style={{ width: '12px', height: '12px' }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            zIndex: 20,
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: '8px',
            padding: '4px 0',
            boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
            minWidth: '160px',
          }}
        >
          {options.map((opt) => {
            const active = selected === opt.value
            return (
              <button
                key={opt.value}
                onClick={() => {
                  onChange(active ? '' : opt.value)
                  setOpen(false)
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '6px 12px',
                  textAlign: 'left',
                  fontSize: '12px',
                  color: active ? '#E94D35' : '#121212',
                  fontWeight: active ? 500 : 400,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'background 100ms',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#FAFAFA' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              >
                <span
                  style={{
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    border: active ? '4px solid #E94D35' : '1.5px solid #D1D5DB',
                    background: 'transparent',
                    flexShrink: 0,
                  }}
                />
                {opt.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Main filter bar                                                     */
/* ------------------------------------------------------------------ */

const STAGE_OPTIONS = [
  { value: 'identified', label: 'Identified' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'engaged', label: 'Engaged' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'committed', label: 'Committed' },
  { value: 'closed', label: 'Closed' },
]

const FIT_TIER_OPTIONS = [
  { value: 'Strong', label: 'Strong' },
  { value: 'Medium', label: 'Medium' },
  { value: 'Weak', label: 'Weak' },
]

const RELATIONSHIP_TYPE_OPTIONS = [
  { value: 'prospect', label: 'Prospect' },
  { value: 'customer', label: 'Customer' },
  { value: 'partner', label: 'Partner' },
  { value: 'investor', label: 'Investor' },
  { value: 'advisor', label: 'Advisor' },
]

const SOURCE_OPTIONS = [
  { value: 'manual', label: 'Manual' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'email', label: 'Email' },
  { value: 'gtm_scrape', label: 'GTM Scrape' },
]

export interface PipelineFilterBarProps {
  stage: string[]
  onStageChange: (values: string[]) => void
  fitTier: string[]
  onFitTierChange: (values: string[]) => void
  relationshipType: string[]
  onRelationshipTypeChange: (values: string[]) => void
  source: string
  onSourceChange: (value: string) => void
  onClear: () => void
}

export function PipelineFilterBar({
  stage,
  onStageChange,
  fitTier,
  onFitTierChange,
  relationshipType,
  onRelationshipTypeChange,
  source,
  onSourceChange,
  onClear,
}: PipelineFilterBarProps) {
  const hasAnyFilter = stage.length > 0 || fitTier.length > 0 || relationshipType.length > 0 || source !== ''

  return (
    <div
      className="flex items-center gap-2"
      style={{
        padding: '6px 0',
        borderBottom: '1px solid #F3F4F6',
        marginBottom: '4px',
      }}
    >
      <MultiSelectFilter
        label="Stage"
        options={STAGE_OPTIONS}
        selected={stage}
        onChange={onStageChange}
      />
      <MultiSelectFilter
        label="Fit Tier"
        options={FIT_TIER_OPTIONS}
        selected={fitTier}
        onChange={onFitTierChange}
      />
      <MultiSelectFilter
        label="Relationship"
        options={RELATIONSHIP_TYPE_OPTIONS}
        selected={relationshipType}
        onChange={onRelationshipTypeChange}
      />
      <SingleSelectFilter
        label="Source"
        options={SOURCE_OPTIONS}
        selected={source}
        onChange={onSourceChange}
      />

      {hasAnyFilter && (
        <button
          onClick={onClear}
          style={{
            background: 'none',
            border: 'none',
            color: '#E94D35',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer',
            padding: '4px 8px',
          }}
        >
          Clear
        </button>
      )}
    </div>
  )
}
