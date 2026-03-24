/**
 * OnboardingPage - 5-moment onboarding orchestrator.
 *
 * Moments: arrive -> discover -> align -> experience -> land
 * No step numbers, no progress bars. Just the current moment,
 * centered, with generous whitespace. Subtle dot indicator at bottom.
 */

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useOnboarding } from '@/features/onboarding/hooks/useOnboarding'
import { MomentArrive } from '@/features/onboarding/components/MomentArrive'
import { MomentDiscover } from '@/features/onboarding/components/MomentDiscover'
import { MomentAlign } from '@/features/onboarding/components/MomentAlign'
import { MomentExperience } from '@/features/onboarding/components/MomentExperience'
import { MomentLand } from '@/features/onboarding/components/MomentLand'
import { colors } from '@/lib/design-tokens'

// ---------------------------------------------------------------------------
// Moment type + ordering
// ---------------------------------------------------------------------------

type Moment = 'arrive' | 'discover' | 'align' | 'experience' | 'land'

const MOMENTS: Moment[] = ['arrive', 'discover', 'align', 'experience', 'land']

// ---------------------------------------------------------------------------
// Dot progress indicator
// ---------------------------------------------------------------------------

function MomentDots({ current }: { current: Moment }) {
  const currentIndex = MOMENTS.indexOf(current)

  return (
    <div className="flex items-center justify-center gap-2">
      {MOMENTS.map((m, i) => (
        <div
          key={m}
          className="h-2 w-2 rounded-full transition-colors duration-300"
          style={{
            backgroundColor: i <= currentIndex
              ? 'var(--brand-coral)'
              : 'var(--subtle-border)',
          }}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export function OnboardingPage() {
  const navigate = useNavigate()
  const onboarding = useOnboarding()
  const [moment, setMoment] = useState<Moment>('arrive')
  const [briefingHtml, setBriefingHtml] = useState<string | null>(null)

  const {
    crawlItems,
    crawlTotal,
    crawlStatus,
    phase: crawlPhase,
    error,
    startCrawl,
    parseStreams,
    confirmStreams,
    parsedStreams,
    retry,
  } = onboarding

  // ---- Moment handlers ----

  const handleArriveComplete = useCallback(
    (url: string) => {
      startCrawl(url)
      setMoment('discover')
    },
    [startCrawl],
  )

  const handleDiscoverComplete = useCallback(() => {
    setMoment('align')
  }, [])

  const handleAlignComplete = useCallback(() => {
    setMoment('experience')
  }, [])

  const handleExperienceComplete = useCallback((html?: string) => {
    if (html) setBriefingHtml(html)
    setMoment('land')
  }, [])

  const handleLandComplete = useCallback(() => {
    navigate('/')
  }, [navigate])

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-6"
      style={{ background: colors.pageBg }}
    >
      {/* Error banner */}
      {error && (
        <div className="mb-6 w-full max-w-xl rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-2 text-sm font-medium hover:underline"
            style={{ color: colors.brandCoral }}
          >
            Try again
          </button>
        </div>
      )}

      {/* Current moment */}
      <div className="w-full flex-1 flex items-center justify-center py-12">
        {moment === 'arrive' && (
          <MomentArrive onComplete={handleArriveComplete} />
        )}

        {moment === 'discover' && (
          <MomentDiscover
            crawlItems={crawlItems}
            crawlTotal={crawlTotal}
            crawlStatus={crawlStatus}
            isComplete={crawlPhase === 'crawl_complete'}
            onComplete={handleDiscoverComplete}
          />
        )}

        {moment === 'align' && (
          <MomentAlign
            onComplete={handleAlignComplete}
            parseStreams={parseStreams}
            confirmStreams={confirmStreams}
            parsedStreams={parsedStreams}
          />
        )}

        {moment === 'experience' && (
          <MomentExperience onComplete={handleExperienceComplete} />
        )}

        {moment === 'land' && (
          <MomentLand
            briefingHtml={briefingHtml}
            onComplete={handleLandComplete}
          />
        )}
      </div>

      {/* Subtle dot progress at bottom */}
      <div className="pb-8">
        <MomentDots current={moment} />
      </div>
    </div>
  )
}
