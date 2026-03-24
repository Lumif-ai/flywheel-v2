import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { UrlInput } from '@/features/onboarding/components/UrlInput'
import { LiveCrawl } from '@/features/onboarding/components/LiveCrawl'
import { StreamCreator } from '@/features/onboarding/components/StreamCreator'
import { OnboardingMeetingPrep } from '@/features/onboarding/components/OnboardingMeetingPrep'
import { useOnboarding } from '@/features/onboarding/hooks/useOnboarding'
import { Button } from '@/components/ui/button'

// Progress step definitions
const STEPS = [
  { key: 'crawl', label: 'Discover' },
  { key: 'streams', label: 'Organize' },
  { key: 'prep', label: 'Prepare' },
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
    crawlStatus,
    parsedStreams,
    briefingHtml,
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

  // Brief step is now shown inline — no auto-navigate

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
            crawlStatus={crawlStatus}
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

      {/* Step: Meeting Prep — first skill experience */}
      {phase === 'meeting_notes' && (
        <div className="w-full max-w-2xl">
          <OnboardingMeetingPrep
            onComplete={goToBriefing}
            onSkip={skipToBriefing}
          />
        </div>
      )}

      {/* Step: Brief — show the meeting prep briefing full-width */}
      {phase === 'first_briefing' && (
        <div className="w-full max-w-3xl flex flex-col items-center">
          {briefingHtml ? (
            <>
              <div
                className="w-full rounded-lg border border-border bg-background p-8 overflow-y-auto prose prose-sm dark:prose-invert"
                style={{ maxHeight: '70vh' }}
                dangerouslySetInnerHTML={{ __html: briefingHtml }}
              />
              <div className="mt-6 text-center space-y-3">
                <Button
                  onClick={() => navigate('/')}
                  size="lg"
                  className="gap-2 px-8"
                >
                  Enter your workspace
                </Button>
                <p className="text-xs text-muted-foreground">
                  This briefing is saved — find it anytime in your workspace
                </p>
              </div>
            </>
          ) : (
            <div className="text-center space-y-4">
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                Welcome to your workspace
              </h2>
              <p className="text-muted-foreground">
                Start using skills to build intelligence that compounds over time
              </p>
              <Button
                onClick={() => navigate('/')}
                size="lg"
                className="gap-2 px-8"
              >
                Enter workspace
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
