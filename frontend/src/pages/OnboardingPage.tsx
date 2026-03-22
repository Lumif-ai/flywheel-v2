import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { UrlInput } from '@/features/onboarding/components/UrlInput'
import { LiveCrawl } from '@/features/onboarding/components/LiveCrawl'
import { StreamCreator } from '@/features/onboarding/components/StreamCreator'
import { useOnboarding } from '@/features/onboarding/hooks/useOnboarding'

// Progress step definitions
const STEPS = [
  { key: 'crawl', label: 'Discover' },
  { key: 'streams', label: 'Organize' },
  { key: 'meetings', label: 'Connect' },
  { key: 'briefing', label: 'Brief' },
] as const

function getStepIndex(phase: string): number {
  switch (phase) {
    case 'url_input':
    case 'crawling':
    case 'crawl_complete':
      return 0
    case 'stream_input':
    case 'stream_confirm':
      return 1
    case 'meeting_notes':
      return 2
    case 'first_briefing':
      return 3
    default:
      return 0
  }
}

function ProgressDots({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center justify-center gap-3 mb-8">
      {STEPS.map((step, i) => (
        <div key={step.key} className="flex items-center gap-3">
          <div className="flex flex-col items-center gap-1">
            <div
              className={`h-2.5 w-2.5 rounded-full transition-colors duration-300 ${
                i <= currentStep ? 'bg-primary' : 'bg-muted'
              }`}
            />
            <span
              className={`text-xs ${
                i <= currentStep ? 'text-foreground' : 'text-muted-foreground'
              }`}
            >
              {step.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={`h-px w-8 mt-[-14px] ${
                i < currentStep ? 'bg-primary' : 'bg-muted'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  )
}

function SkipLink({ onClick, label = 'Skip for now' }: { onClick: () => void; label?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-6 text-sm text-muted-foreground hover:text-foreground transition-colors"
    >
      {label}
    </button>
  )
}

export function OnboardingPage() {
  const navigate = useNavigate()
  const onboarding = useOnboarding()

  const {
    phase,
    crawlItems,
    crawlTotal,
    parsedStreams,
    error,
    loading,
    startCrawl,
    proceedToStreams,
    parseStreams,
    updateStream,
    removeStream,
    addStream,
    confirmStreams,
    skipToMeetings,
    skipToBriefing,
    goToBriefing,
    retry,
  } = onboarding

  // Navigate to briefing when phase reaches first_briefing
  useEffect(() => {
    if (phase === 'first_briefing') {
      navigate('/')
    }
  }, [phase, navigate])

  const currentStep = getStepIndex(phase)

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center px-4 py-12">
      {/* Progress dots (hidden on initial URL input) */}
      {phase !== 'url_input' && <ProgressDots currentStep={currentStep} />}

      {/* Error banner */}
      {error && (
        <div className="mb-6 w-full max-w-xl rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-2 text-sm font-medium text-primary hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Step: URL Input */}
      {phase === 'url_input' && <UrlInput onSubmit={startCrawl} />}

      {/* Step: Crawling / Crawl Complete */}
      {(phase === 'crawling' || phase === 'crawl_complete') && (
        <div className="w-full max-w-xl flex flex-col items-center">
          <LiveCrawl
            crawlItems={crawlItems}
            crawlTotal={crawlTotal}
            isComplete={phase === 'crawl_complete'}
            onContinue={proceedToStreams}
          />
          {phase === 'crawl_complete' && (
            <SkipLink onClick={skipToMeetings} label="Skip to meetings" />
          )}
        </div>
      )}

      {/* Step: Stream Input / Confirm */}
      {(phase === 'stream_input' || phase === 'stream_confirm') && (
        <div className="w-full max-w-xl flex flex-col items-center">
          <StreamCreator
            phase={phase}
            parsedStreams={parsedStreams}
            loading={loading}
            error={error}
            onParse={parseStreams}
            onUpdate={updateStream}
            onRemove={removeStream}
            onAdd={addStream}
            onConfirm={confirmStreams}
          />
          <SkipLink onClick={skipToMeetings} />
        </div>
      )}

      {/* Step: Meeting Notes (Plan 03 placeholder) */}
      {phase === 'meeting_notes' && (
        <div className="w-full max-w-xl flex flex-col items-center text-center space-y-4">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Add meeting notes
          </h2>
          <p className="text-muted-foreground">
            Paste or upload meeting notes to enrich your workspace intelligence.
          </p>
          <p className="text-sm text-muted-foreground italic">
            Coming in Plan 03
          </p>
          <button
            type="button"
            onClick={goToBriefing}
            className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Go to briefing
          </button>
          <SkipLink onClick={skipToBriefing} />
        </div>
      )}
    </div>
  )
}
