import { UrlInput } from '@/features/onboarding/components/UrlInput'
import { CrawlStream } from '@/features/onboarding/components/CrawlStream'
import { CompanyProfile } from '@/features/onboarding/components/CompanyProfile'
import { SignupPrompt } from '@/features/onboarding/components/SignupPrompt'
import { useCrawl } from '@/features/onboarding/hooks/useCrawl'

export function OnboardingPage() {
  const {
    phase,
    crawlEvents,
    companyData,
    error,
    startCrawl,
    runFirstSkill,
    retry,
  } = useCrawl()

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center px-4 py-12">
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

      {/* Idle: URL input centered */}
      {phase === 'idle' && <UrlInput onSubmit={startCrawl} />}

      {/* Crawling: URL input (disabled) + stream below */}
      {phase === 'crawling' && (
        <div className="w-full space-y-8">
          <UrlInput onSubmit={startCrawl} disabled />
          <CrawlStream events={crawlEvents} />
        </div>
      )}

      {/* Profile: show company data with skill CTA */}
      {phase === 'profile' && companyData && (
        <CompanyProfile
          company={companyData}
          onRunSkill={runFirstSkill}
        />
      )}

      {/* First run: profile with running indicator */}
      {phase === 'first_run' && companyData && (
        <CompanyProfile
          company={companyData}
          onRunSkill={runFirstSkill}
          isRunning
        />
      )}

      {/* Signup: prompt to save results */}
      {phase === 'signup' && <SignupPrompt />}
    </div>
  )
}
