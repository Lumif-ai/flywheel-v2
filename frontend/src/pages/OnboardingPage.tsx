/**
 * OnboardingPage - 5-moment onboarding orchestrator.
 *
 * Moments: arrive -> discover -> align -> experience -> land
 * No step numbers, no progress bars. Just the current moment,
 * centered, with generous whitespace. Subtle dot indicator at bottom.
 */

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { Loader2 } from 'lucide-react'
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
    retry,
    // Edit mode (Plan 02)
    editMode,
    editedItems,
    removeItem,
    addItem,
    editItem,
    confirmEdits,
    // Priorities (Plan 02)
    selectedPriorities,
    togglePriority,
    confirmPriorities,
    priorityOptions,
    // Cache-first (Plan 03)
    cacheChecking,
    cacheResult,
    startWithCacheCheck,
  } = onboarding

  // ---- Moment handlers ----

  const handleArriveComplete = useCallback(
    async (url: string) => {
      setMoment('discover')
      await startWithCacheCheck(url)
    },
    [startWithCacheCheck],
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
          <MomentArrive onComplete={handleArriveComplete} cacheChecking={cacheChecking} />
        )}

        {moment === 'discover' && (
          <div className="w-full" style={{ maxWidth: '640px' }}>
            {/* Cache status banner */}
            {cacheResult?.exists && (
              <div
                style={{
                  textAlign: 'center',
                  marginBottom: '12px',
                  fontSize: '14px',
                  color: colors.secondaryText,
                }}
              >
                {cacheResult.last_updated &&
                  (Date.now() - new Date(cacheResult.last_updated).getTime()) / (1000 * 60 * 60 * 24) < 7 ? (
                  <span>Welcome back — here&apos;s what we know about {cacheResult.domain}</span>
                ) : (
                  <span className="inline-flex items-center gap-1.5">
                    Here&apos;s what we know — refreshing for latest
                    <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: colors.secondaryText }} />
                  </span>
                )}
              </div>
            )}
            <MomentDiscover
              crawlItems={crawlItems}
              crawlTotal={crawlTotal}
              crawlStatus={crawlStatus}
              isComplete={crawlPhase === 'crawl_complete'}
              editMode={editMode}
              editedItems={editedItems}
              onComplete={handleDiscoverComplete}
              onRemoveItem={removeItem}
              onAddItem={addItem}
              onEditItem={editItem}
              onConfirmEdits={confirmEdits}
            />
          </div>
        )}

        {moment === 'align' && (
          <MomentAlign
            onComplete={handleAlignComplete}
            selectedPriorities={selectedPriorities}
            onTogglePriority={togglePriority}
            onConfirmPriorities={confirmPriorities}
            priorityOptions={priorityOptions}
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
