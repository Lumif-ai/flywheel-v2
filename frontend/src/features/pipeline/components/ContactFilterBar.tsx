import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

/* ------------------------------------------------------------------ */
/* Single-select dropdown (copied from PipelineFilterBar)              */
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
        {hasActive ? `${label}: ${selected}` : label}
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
/* Company text filter                                                 */
/* ------------------------------------------------------------------ */

interface CompanyFilterProps {
  value: string
  onChange: (value: string) => void
}

function CompanyFilter({ value, onChange }: CompanyFilterProps) {
  const [editing, setEditing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
    }
  }, [editing])

  const hasActive = value !== ''

  if (!editing && !hasActive) {
    return (
      <button
        onClick={() => setEditing(true)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 10px',
          borderRadius: '6px',
          border: '1px solid #E5E7EB',
          background: '#FFFFFF',
          color: '#6B7280',
          fontSize: '12px',
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'all 150ms',
        }}
      >
        Company
        <ChevronDown style={{ width: '12px', height: '12px' }} />
      </button>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => { if (!value) setEditing(false) }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            onChange('')
            setEditing(false)
          }
        }}
        placeholder="Company..."
        style={{
          padding: '4px 10px',
          borderRadius: '6px',
          border: hasActive ? '1px solid #E94D35' : '1px solid #E5E7EB',
          background: hasActive ? '#FEF2F0' : '#FFFFFF',
          color: hasActive ? '#E94D35' : '#121212',
          fontSize: '12px',
          fontWeight: 500,
          outline: 'none',
          width: '140px',
        }}
      />
      {hasActive && (
        <button
          onClick={() => { onChange(''); setEditing(false) }}
          style={{
            position: 'absolute',
            right: '6px',
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            color: '#E94D35',
            fontSize: '12px',
            cursor: 'pointer',
            padding: '0 2px',
            lineHeight: 1,
          }}
        >
          &times;
        </button>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Filter option constants                                             */
/* ------------------------------------------------------------------ */

const STATUS_OPTIONS = [
  { value: 'drafted', label: 'Drafted' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'replied', label: 'Replied' },
  { value: 'bounced', label: 'Bounced' },
]

const CHANNEL_OPTIONS = [
  { value: 'email', label: 'Email' },
  { value: 'linkedin', label: 'LinkedIn' },
]

const VARIANT_OPTIONS = [
  { value: 'direct', label: 'Direct' },
  { value: 'intro', label: 'Intro' },
]

const STEP_OPTIONS = [
  { value: '1', label: 'Step 1' },
  { value: '2', label: 'Step 2' },
  { value: '3', label: 'Step 3' },
  { value: '4', label: 'Step 4' },
  { value: '5', label: 'Step 5' },
]

/* ------------------------------------------------------------------ */
/* Contact Filter Bar                                                  */
/* ------------------------------------------------------------------ */

export interface ContactFilterBarProps {
  company: string
  onCompanyChange: (value: string) => void
  status: string
  onStatusChange: (value: string) => void
  channel: string
  onChannelChange: (value: string) => void
  variant: string
  onVariantChange: (value: string) => void
  stepNumber: string
  onStepNumberChange: (value: string) => void
  onClear: () => void
}

export function ContactFilterBar({
  company,
  onCompanyChange,
  status,
  onStatusChange,
  channel,
  onChannelChange,
  variant,
  onVariantChange,
  stepNumber,
  onStepNumberChange,
  onClear,
}: ContactFilterBarProps) {
  const hasAnyFilter = company !== '' || status !== '' || channel !== '' || variant !== '' || stepNumber !== ''

  return (
    <div
      className="flex items-center gap-2"
      style={{
        padding: '6px 0',
        borderBottom: '1px solid #F3F4F6',
        marginBottom: '4px',
      }}
    >
      <CompanyFilter value={company} onChange={onCompanyChange} />
      <SingleSelectFilter
        label="Status"
        options={STATUS_OPTIONS}
        selected={status}
        onChange={onStatusChange}
      />
      <SingleSelectFilter
        label="Channel"
        options={CHANNEL_OPTIONS}
        selected={channel}
        onChange={onChannelChange}
      />
      <SingleSelectFilter
        label="Variant"
        options={VARIANT_OPTIONS}
        selected={variant}
        onChange={onVariantChange}
      />
      <SingleSelectFilter
        label="Step"
        options={STEP_OPTIONS}
        selected={stepNumber}
        onChange={onStepNumberChange}
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
