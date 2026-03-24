/**
 * MomentArrive - First onboarding moment.
 *
 * A magic-portal URL input: unified search bar with embedded Go button,
 * subtle coral glow on focus, no visible borders at rest.
 * Inspired by Vercel's deploy input and Linear's onboarding.
 */

import { useState, useCallback, type KeyboardEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses } from '@/lib/animations'

interface MomentArriveProps {
  onComplete: (url: string) => void
}

function normalizeUrl(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

const shadowRest = '0 2px 8px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04)'
const shadowFocus =
  '0 4px 16px rgba(233,77,53,0.12), 0 0 0 2px rgba(233,77,53,0.2)'

export function MomentArrive({ onComplete }: MomentArriveProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [focused, setFocused] = useState(false)

  const handleSubmit = useCallback(() => {
    const url = normalizeUrl(value)
    if (!url) return
    if (!isValidUrl(url)) {
      setError('Please enter a valid URL')
      return
    }
    setError(null)
    onComplete(url)
  }, [value, onComplete])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  const canSubmit = value.trim().length > 0

  return (
    <div
      className={animationClasses.fadeSlideUp}
      style={{
        maxWidth: spacing.maxReading,
        width: '100%',
        margin: '0 auto',
        textAlign: 'center',
      }}
    >
      <div style={{ marginBottom: spacing.section }}>
        <h1
          style={{
            fontSize: '36px',
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            color: colors.headingText,
            marginBottom: spacing.tight,
          }}
        >
          Paste your company URL
        </h1>
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
          }}
        >
          We'll discover everything about your company in seconds
        </p>
      </div>

      {/* Unified search bar container */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--card-bg)',
          borderRadius: '16px',
          boxShadow: focused ? shadowFocus : shadowRest,
          transition: 'box-shadow 200ms ease-out',
          padding: '6px 6px 6px 20px',
          marginBottom: error ? '8px' : '0',
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder="acme.com"
          autoFocus
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontSize: '16px',
            lineHeight: '24px',
            color: 'var(--heading-text)',
            padding: '10px 0',
            minWidth: 0,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: canSubmit ? colors.brandCoral : 'rgba(233,77,53,0.4)',
            color: '#fff',
            border: 'none',
            borderRadius: '12px',
            padding: '10px 20px',
            fontSize: '15px',
            fontWeight: 600,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            transition: 'background-color 150ms ease, opacity 150ms ease',
            opacity: canSubmit ? 1 : 0.7,
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          Go
          <ArrowRight style={{ width: '16px', height: '16px' }} />
        </button>
      </div>

      {error && (
        <p style={{ color: colors.error, fontSize: '14px', marginTop: '8px' }}>
          {error}
        </p>
      )}

      <p
        style={{
          color: 'var(--secondary-text)',
          fontSize: '13px',
          marginTop: '12px',
        }}
      >
        Try: acme.com, stripe.com, or your company's website
      </p>
    </div>
  )
}
