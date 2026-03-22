import { useMemo } from 'react'
import { useBriefing } from '../hooks/useBriefing'
import { BriefingCard } from './BriefingCard'
import { KnowledgeHealthBar } from './KnowledgeHealthBar'
import { GlobalChatInput } from './GlobalChatInput'
import { SoftSignupCard, isSignupCardDismissed } from '@/features/onboarding/components/SoftSignupCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Link } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { InboxIcon, Calendar, ArrowRight } from 'lucide-react'

export function BriefingPage() {
  const { data, isLoading, error } = useBriefing()
  const user = useAuthStore(state => state.user)

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

        {/* Cards Grid */}
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
        ) : data?.cards && data.cards.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.cards.map((card, i) => (
              <BriefingCard key={i} card={card} />
            ))}
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

        {/* Nudge */}
        {data?.nudge && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
            <p className="text-sm text-blue-800">
              {JSON.stringify(data.nudge)}
            </p>
          </div>
        )}
      </div>

      {/* Calendar connect suggestion for anonymous users */}
      {isAnonymous && (
        <div className="mx-6 mb-4 rounded-lg border border-dashed p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Connect your calendar</p>
              <p className="text-xs text-muted-foreground">
                Auto-detect meetings and prep briefings
              </p>
            </div>
          </div>
          <Link
            to="/settings"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            Set up
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      {/* Global Chat Input - pinned at bottom */}
      <div className="border-t bg-background p-4">
        <GlobalChatInput />
      </div>
    </div>
  )
}
