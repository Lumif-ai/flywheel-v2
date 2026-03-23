import { useMemo } from 'react'
import { useBriefing } from '../hooks/useBriefing'
import { useStreams } from '../hooks/useStreams'
import { BriefingCard } from './BriefingCard'
import { PersonalGapCard } from './PersonalGapCard'
import { NudgeCard } from './NudgeCard'
import { KnowledgeHealthBar } from './KnowledgeHealthBar'
import { GlobalChatInput } from './GlobalChatInput'
import { SoftSignupCard, isSignupCardDismissed } from '@/features/onboarding/components/SoftSignupCard'
import { StreamDensityCard } from '@/features/streams/components/DensityIndicator'
import { Skeleton } from '@/components/ui/skeleton'
import { Link } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { InboxIcon } from 'lucide-react'

export function BriefingPage() {
  const { data, isLoading, error } = useBriefing()
  const { data: streamsData } = useStreams()
  const user = useAuthStore(state => state.user)

  const streams = streamsData?.items ?? []

  const isAnonymous = useMemo(() => {
    if (!user) return true
    return (user as Record<string, unknown>).is_anonymous === true
  }, [user])

  const showSignupCard = isAnonymous && !isSignupCardDismissed()

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-sm text-destructive">
          Failed to load briefing. Please try again later.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {/* Soft signup card for anonymous users */}
        {showSignupCard && <SoftSignupCard />}

        {/* Greeting */}
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-40" />
          </div>
        ) : (
          <div>
            <h1 className="text-2xl font-bold">{data?.greeting}</h1>
            <p className="text-sm text-muted-foreground">
              {new Date().toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        )}

        {/* Knowledge Health */}
        {isLoading ? (
          <div className="space-y-1.5">
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-4 w-48" />
          </div>
        ) : data?.knowledge_health ? (
          <KnowledgeHealthBar health={data.knowledge_health} />
        ) : null}

        {/* Nudge */}
        {data?.nudge && <NudgeCard nudge={data.nudge} />}

        {/* Your Streams - per-stream density */}
        {streams.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">Your Streams</h2>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {streams.map((stream) => (
                <Link
                  key={stream.id}
                  to={`/streams/${stream.id}`}
                  className="rounded-xl border bg-card p-4 transition-colors hover:bg-accent/50"
                >
                  <p className="mb-2 text-sm font-medium truncate">{stream.name}</p>
                  <StreamDensityCard
                    densityScore={stream.density_score}
                    details={stream.density_details}
                    compact
                  />
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Cards Grid */}
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
        ) : data?.cards && data.cards.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.cards.map((card, i) => {
              if (card.card_type === 'personal_gap') {
                // Parse teamCount/myCount from reason field ("X entries from other members, Y from you")
                let teamCount = 0
                let myCount = 0
                if (card.reason) {
                  const teamMatch = card.reason.match(/(\d+)\s+entr(?:y|ies)\s+from\s+other/)
                  const myMatch = card.reason.match(/(\d+)\s+from\s+you/)
                  if (teamMatch) teamCount = parseInt(teamMatch[1], 10)
                  if (myMatch) myCount = parseInt(myMatch[1], 10)
                }
                return (
                  <PersonalGapCard
                    key={i}
                    title={card.title}
                    detail={card.body}
                    streamId={card.stream_id ?? ''}
                    teamCount={teamCount}
                    myCount={myCount}
                  />
                )
              }
              return <BriefingCard key={i} card={card} />
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <InboxIcon className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-lg font-medium">Your workspace is ready</h2>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Start by creating a work stream to organize your knowledge around
              the projects and accounts that matter most.
            </p>
            <Link
              to="/streams/new"
              className="mt-4 text-sm text-primary hover:underline"
            >
              Create a work stream
            </Link>
          </div>
        )}

      </div>

      {/* Global Chat Input - pinned at bottom */}
      <div className="border-t bg-background p-4">
        <GlobalChatInput />
      </div>
    </div>
  )
}
