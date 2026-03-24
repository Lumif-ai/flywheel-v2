/**
 * MomentAlign - Third onboarding moment.
 *
 * One question, free text. User describes what's top of mind.
 * Parses input into focus areas and auto-creates them via the
 * existing streams/parse API. Shows confirmation with stagger.
 * Auto-advances after 1.5 seconds.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses, staggerDelay } from '@/lib/animations'
import type { ParsedStream } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentAlignProps {
  onComplete: () => void
  parseStreams: (input: string) => Promise<void>
  confirmStreams: () => Promise<void>
  parsedStreams: ParsedStream[]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentAlign({
  onComplete,
  parseStreams,
  confirmStreams,
  parsedStreams,
}: MomentAlignProps) {
  const [value, setValue] = useState('')
  const [phase, setPhase] = useState<'input' | 'parsing' | 'confirming' | 'done'>('input')
  const [createdNames, setCreatedNames] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const autoAdvanceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // When parsedStreams arrive (from parseStreams call), auto-confirm them
  useEffect(() => {
    if (phase === 'parsing' && parsedStreams.length > 0) {
      setPhase('confirming')
      setCreatedNames(parsedStreams.map((s) => s.name))
      // Auto-confirm the streams
      confirmStreams()
        .then(() => {
          setPhase('done')
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Failed to create focus areas')
          setPhase('input')
        })
    }
  }, [parsedStreams, phase, confirmStreams])

  // Auto-advance 1.5s after done
  useEffect(() => {
    if (phase === 'done') {
      autoAdvanceRef.current = setTimeout(() => {
        onComplete()
      }, 1500)
    }
    return () => {
      if (autoAdvanceRef.current) clearTimeout(autoAdvanceRef.current)
    }
  }, [phase, onComplete])

  const handleSubmit = useCallback(async () => {
    if (!value.trim()) return
    setPhase('parsing')
    setError(null)
    try {
      await parseStreams(value.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse focus areas')
      setPhase('input')
    }
  }, [value, parseStreams])

  // ---- Input phase ----
  if (phase === 'input' || phase === 'parsing') {
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
            What's top of mind for your team right now?
          </h1>
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            We'll organize your workspace around your priorities
          </p>
        </div>

        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Hiring engineers and closing Series A..."
          rows={4}
          className="resize-none text-base mb-4"
          disabled={phase === 'parsing'}
        />

        {error && (
          <p className="text-sm mb-3" style={{ color: colors.error }}>
            {error}
          </p>
        )}

        <Button
          onClick={handleSubmit}
          disabled={phase === 'parsing' || !value.trim()}
          size="lg"
          className="gap-2 px-8"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            border: 'none',
            color: 'white',
          }}
        >
          {phase === 'parsing' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating focus areas...
            </>
          ) : (
            'Continue'
          )}
        </Button>
      </div>
    )
  }

  // ---- Confirming / Done phase — show created focus areas ----
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
      <h1
        style={{
          fontSize: typography.pageTitle.size,
          fontWeight: typography.pageTitle.weight,
          lineHeight: typography.pageTitle.lineHeight,
          color: colors.headingText,
          marginBottom: spacing.section,
        }}
      >
        {phase === 'confirming' ? 'Setting up your focus areas...' : 'Focus areas created'}
      </h1>

      <div className="flex flex-wrap justify-center gap-3">
        {createdNames.map((name, i) => (
          <span
            key={name}
            className={`${animationClasses.fadeSlideUp} inline-flex items-center rounded-full px-4 py-2`}
            style={{
              animationDelay: staggerDelay(i),
              animationFillMode: 'both',
              fontSize: typography.body.size,
              fontWeight: '500',
              background: colors.brandTint,
              color: colors.headingText,
              border: `1px solid ${colors.subtleBorder}`,
            }}
          >
            {name}
          </span>
        ))}
      </div>

      {phase === 'confirming' && (
        <div className="mt-6 flex justify-center">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: colors.brandCoral }} />
        </div>
      )}
    </div>
  )
}
