/**
 * MomentArrive - First onboarding moment.
 *
 * Clean, minimal URL input. User pastes company URL and submits.
 * Reuses URL normalization/validation logic from UrlInput.
 */

import { useState, useCallback, type KeyboardEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
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

export function MomentArrive({ onComplete }: MomentArriveProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

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
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
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

      <div className="flex gap-3" style={{ marginBottom: spacing.element }}>
        <Input
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder="acme.com"
          className="h-12 text-base"
          autoFocus
        />
        <Button
          onClick={handleSubmit}
          disabled={!value.trim()}
          size="lg"
          className="h-12 gap-2 px-6"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            border: 'none',
            color: 'white',
          }}
        >
          Go
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <p className="text-sm" style={{ color: colors.error }}>
          {error}
        </p>
      )}
    </div>
  )
}
