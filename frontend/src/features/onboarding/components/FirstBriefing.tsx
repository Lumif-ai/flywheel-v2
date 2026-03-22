/**
 * FirstBriefing - Transition screen after meeting notes (or skip)
 * before redirecting to the main briefing page.
 *
 * Reads from useOnboarding hook state: crawlTotal, createdStreams,
 * and processed notes count for stats display.
 *
 * Auto-redirects after 3 seconds if user doesn't click the CTA.
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { CheckCircle, ArrowRight } from 'lucide-react'
import { useOnboarding } from '../hooks/useOnboarding'

export function FirstBriefing() {
  const navigate = useNavigate()
  const { crawlTotal, createdStreams, goToBriefing } = useOnboarding()
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Derive stats
  const crawlCount = crawlTotal ?? 0
  const streamCount = createdStreams?.length ?? 0

  // Auto-redirect after 3 seconds
  useEffect(() => {
    redirectTimerRef.current = setTimeout(() => {
      navigate('/')
    }, 3000)

    return () => {
      if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current)
    }
  }, [navigate])

  const handleClick = () => {
    if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current)
    goToBriefing()
  }

  return (
    <div className="max-w-2xl mx-auto text-center space-y-8 py-12">
      {/* Success icon */}
      <div className="flex justify-center">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
          <CheckCircle className="w-10 h-10 text-green-500" />
        </div>
      </div>

      {/* Heading */}
      <div className="space-y-3">
        <h1 className="text-3xl font-bold">Your workspace is ready</h1>
        <p className="text-muted-foreground text-lg">
          {crawlCount > 0 && <>{crawlCount} intelligence items from crawl</>}
          {crawlCount > 0 && streamCount > 0 && <>, </>}
          {streamCount > 0 && <>{streamCount} work streams created</>}
        </p>
      </div>

      {/* Density bars for each created stream */}
      {createdStreams.length > 0 && (
        <div className="space-y-3 max-w-md mx-auto text-left">
          {createdStreams.map(stream => (
            <div key={stream.id} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{stream.name}</span>
                <span className="text-muted-foreground">
                  {stream.density_score}%
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-1000 ease-out delay-300"
                  style={{
                    width: `${Math.min(stream.density_score, 100)}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CTA */}
      <button
        onClick={handleClick}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
      >
        See your first briefing
        <ArrowRight className="w-4 h-4" />
      </button>

      {/* Auto-redirect hint */}
      <p className="text-xs text-muted-foreground">
        Redirecting automatically in a few seconds...
      </p>
    </div>
  )
}
