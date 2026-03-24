/**
 * MomentAlign - Third onboarding moment.
 *
 * Shows 3 skills-backed priority option cards for multi-select.
 * No free text input. Users select priorities, click Continue,
 * and focus areas are created from selected options.
 */

import { useState, useCallback } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses, staggerDelay } from '@/lib/animations'
import type { PriorityOption } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentAlignProps {
  onComplete: () => void
  selectedPriorities: string[]
  onTogglePriority: (id: string) => void
  onConfirmPriorities: () => Promise<void>
  priorityOptions: PriorityOption[]
}

// ---------------------------------------------------------------------------
// Priority Card
// ---------------------------------------------------------------------------

function PriorityCard({
  option,
  selected,
  index,
  onToggle,
}: {
  option: PriorityOption
  selected: boolean
  index: number
  onToggle: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle() } }}
      className={`${animationClasses.fadeSlideUp} relative rounded-lg p-5 cursor-pointer transition-all duration-200`}
      style={{
        animationDelay: staggerDelay(index),
        animationFillMode: 'both',
        background: selected ? colors.brandTint : colors.cardBg,
        border: `1px solid ${selected ? 'transparent' : colors.subtleBorder}`,
        borderLeft: selected ? `3px solid ${colors.brandCoral}` : `1px solid ${colors.subtleBorder}`,
        boxShadow: selected ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h3
            style={{
              fontSize: '18px',
              fontWeight: '600',
              color: colors.headingText,
              marginBottom: '4px',
            }}
          >
            {option.label}
          </h3>
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
              lineHeight: typography.body.lineHeight,
              marginBottom: '8px',
            }}
          >
            {option.subLabel}
          </p>
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5"
            style={{
              fontSize: typography.caption.size,
              fontWeight: '500',
              background: colors.brandTint,
              color: colors.brandCoral,
            }}
          >
            {option.capabilityCount} capabilities
          </span>
        </div>

        {/* Check icon */}
        {selected && (
          <CheckCircle2
            className="h-5 w-5 shrink-0 mt-0.5"
            style={{ color: colors.brandCoral }}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentAlign({
  onComplete,
  selectedPriorities,
  onTogglePriority,
  onConfirmPriorities,
  priorityOptions,
}: MomentAlignProps) {
  const [confirming, setConfirming] = useState(false)

  const handleConfirm = useCallback(async () => {
    setConfirming(true)
    try {
      await onConfirmPriorities()
      onComplete()
    } catch {
      setConfirming(false)
    }
  }, [onConfirmPriorities, onComplete])

  const selectedCount = selectedPriorities.length

  return (
    <div
      className={animationClasses.fadeSlideUp}
      style={{
        maxWidth: spacing.maxReading,
        width: '100%',
        margin: '0 auto',
      }}
    >
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: spacing.section }}>
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            color: colors.headingText,
            marginBottom: spacing.tight,
          }}
        >
          What matters most right now?
        </h1>
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
          }}
        >
          Select your priorities. We'll configure your workspace around them.
        </p>
      </div>

      {/* Priority cards */}
      <div className="space-y-3" style={{ marginBottom: spacing.element }}>
        {priorityOptions.map((option, i) => (
          <PriorityCard
            key={option.id}
            option={option}
            selected={selectedPriorities.includes(option.id)}
            index={i}
            onToggle={() => onTogglePriority(option.id)}
          />
        ))}
      </div>

      {/* Continue CTA */}
      <div style={{ textAlign: 'center' }}>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={selectedCount === 0 || confirming}
          className="w-full rounded-lg py-3 px-6 text-white font-semibold transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            fontSize: typography.body.size,
            border: 'none',
            cursor: selectedCount === 0 || confirming ? 'not-allowed' : 'pointer',
          }}
        >
          {confirming ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating focus areas...
            </span>
          ) : selectedCount > 1 ? (
            `Continue with ${selectedCount} priorities`
          ) : (
            'Continue'
          )}
        </button>
      </div>
    </div>
  )
}
