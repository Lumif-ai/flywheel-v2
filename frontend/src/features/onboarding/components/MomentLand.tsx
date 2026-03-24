/**
 * MomentLand - Fifth and final onboarding moment.
 *
 * Shows the completed briefing. "Your first briefing is ready."
 * "Enter workspace" button navigates to /.
 */

import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses } from '@/lib/animations'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentLandProps {
  briefingHtml: string | null
  onComplete: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentLand({ briefingHtml, onComplete }: MomentLandProps) {
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
          Your first briefing is ready
        </h1>
      </div>

      {/* Briefing content */}
      {briefingHtml ? (
        <div
          className="rounded-lg border overflow-y-auto prose prose-sm dark:prose-invert"
          style={{
            maxHeight: '50vh',
            padding: spacing.card,
            borderColor: colors.subtleBorder,
            background: colors.cardBg,
          }}
          dangerouslySetInnerHTML={{ __html: briefingHtml }}
        />
      ) : (
        <div
          className="rounded-lg border text-center py-12"
          style={{
            borderColor: colors.subtleBorder,
            background: colors.brandTint,
          }}
        >
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
            Your briefing has been saved to your workspace
          </p>
        </div>
      )}

      {/* Message + CTA */}
      <div style={{ textAlign: 'center', marginTop: spacing.section }}>
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
            marginBottom: spacing.element,
          }}
        >
          This is your first document. Every meeting, every contact, smarter over time.
        </p>

        <Button
          onClick={onComplete}
          size="lg"
          className="gap-2 px-8"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            border: 'none',
            color: 'white',
          }}
        >
          Enter workspace
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
