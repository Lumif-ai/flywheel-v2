import { useMemo, useState, useEffect } from 'react'
import { useBriefing } from '../hooks/useBriefing'
import { useStreams } from '../hooks/useStreams'
import { BriefingCard } from './BriefingCard'
import { PersonalGapCard } from './PersonalGapCard'
import { NudgeCard } from './NudgeCard'
import { KnowledgeHealthBar } from './KnowledgeHealthBar'
import { GlobalChatInput } from './GlobalChatInput'
import { SoftSignupCard, isSignupCardDismissed } from '@/features/onboarding/components/SoftSignupCard'
import { StreamDensityCard } from '@/features/streams/components/DensityIndicator'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { Link } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { InboxIcon, FileText, Building2, Clock } from 'lucide-react'
import { api } from '@/lib/api'
import { spacing, typography, colors } from '@/lib/design-tokens'

interface RecentDocument {
  id: string
  title: string
  doc_type: string
  created_at: string
}

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function BriefingPage() {
  const { data, isLoading, error } = useBriefing()
  const { data: streamsData } = useStreams()
  const user = useAuthStore(state => state.user)

  const [recentDocs, setRecentDocs] = useState<RecentDocument[] | null>(null)
  const [docsLoading, setDocsLoading] = useState(true)

  const streams = streamsData?.items ?? []

  const isAnonymous = useMemo(() => {
    if (!user) return true
    return (user as Record<string, unknown>).is_anonymous === true
  }, [user])

  const showSignupCard = isAnonymous && !isSignupCardDismissed()

  // Fetch recent documents with graceful fallback
  useEffect(() => {
    let cancelled = false
    async function loadDocs() {
      try {
        const result = await api.get<{ documents: RecentDocument[]; total: number }>('/documents/', {
          params: { limit: 3 },
        })
        if (!cancelled) {
          setRecentDocs(result.documents)
          setDocsLoading(false)
        }
      } catch {
        // Documents API not yet available -- show placeholder
        if (!cancelled) {
          setRecentDocs(null)
          setDocsLoading(false)
        }
      }
    }
    loadDocs()
    return () => { cancelled = true }
  }, [])

  const userName = useMemo(() => {
    if (!user) return ''
    const u = user as Record<string, unknown>
    if (u.display_name && typeof u.display_name === 'string') return u.display_name
    if (u.name && typeof u.name === 'string') return u.name
    if (u.email && typeof u.email === 'string') return u.email.split('@')[0]
    return ''
  }, [user])

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
      <div
        className="flex-1 overflow-y-auto page-enter"
        style={{
          padding: `${spacing.pageDesktop}`,
          background: colors.pageBg,
        }}
      >
        <div
          className="mx-auto"
          style={{ maxWidth: spacing.maxGrid }}
        >
          {/* Soft signup card for anonymous users */}
          {showSignupCard && (
            <div style={{ marginBottom: spacing.section }}>
              <SoftSignupCard />
            </div>
          )}

          {/* Greeting Section */}
          {isLoading ? (
            <div className="space-y-2" style={{ marginBottom: spacing.section }}>
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-40" />
            </div>
          ) : (
            <div
              className="flex items-baseline justify-between"
              style={{ marginBottom: spacing.section }}
            >
              <h1
                style={{
                  fontSize: typography.pageTitle.size,
                  fontWeight: typography.pageTitle.weight,
                  lineHeight: typography.pageTitle.lineHeight,
                  letterSpacing: typography.pageTitle.letterSpacing,
                  color: colors.headingText,
                }}
              >
                {getGreeting()}{userName ? `, ${userName}` : ''}.
              </h1>
              <span
                style={{
                  fontSize: typography.caption.size,
                  color: colors.secondaryText,
                }}
              >
                {new Date().toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            </div>
          )}

          {/* Intelligence Health Card */}
          {isLoading ? (
            <div style={{ marginBottom: spacing.section }}>
              <BrandedCard>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-2 w-full" />
                  <Skeleton className="h-4 w-48" />
                </div>
              </BrandedCard>
            </div>
          ) : data?.knowledge_health ? (
            <div style={{ marginBottom: spacing.section }}>
              <BrandedCard hoverable={false}>
                <KnowledgeHealthBar health={data.knowledge_health} />
              </BrandedCard>
            </div>
          ) : null}

          {/* Nudge */}
          {data?.nudge && (
            <div style={{ marginBottom: spacing.section }}>
              <NudgeCard nudge={data.nudge} />
            </div>
          )}

          {/* Your Focus Areas */}
          {streams.length > 0 && (
            <div style={{ marginBottom: spacing.section }}>
              <h2
                style={{
                  fontSize: typography.sectionTitle.size,
                  fontWeight: typography.sectionTitle.weight,
                  lineHeight: typography.sectionTitle.lineHeight,
                  color: colors.headingText,
                  marginBottom: spacing.element,
                }}
              >
                Your Focus Areas
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {streams.filter(s => !s.is_archived).map((stream) => (
                  <Link
                    key={stream.id}
                    to={`/streams/${stream.id}`}
                    className="block no-underline"
                  >
                    <BrandedCard variant="info">
                      <p
                        className="truncate"
                        style={{
                          fontSize: typography.body.size,
                          fontWeight: '500',
                          color: colors.headingText,
                          marginBottom: spacing.tight,
                        }}
                      >
                        {stream.name}
                      </p>
                      <StreamDensityCard
                        densityScore={stream.density_score}
                        details={stream.density_details}
                        compact
                      />
                      <p
                        className="mt-1"
                        style={{
                          fontSize: typography.caption.size,
                          color: colors.secondaryText,
                        }}
                      >
                        {stream.entry_count ?? stream.density_details?.entry_count ?? 0} items
                      </p>
                    </BrandedCard>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Recent Documents */}
          <div style={{ marginBottom: spacing.section }}>
            <h2
              style={{
                fontSize: typography.sectionTitle.size,
                fontWeight: typography.sectionTitle.weight,
                lineHeight: typography.sectionTitle.lineHeight,
                color: colors.headingText,
                marginBottom: spacing.element,
              }}
            >
              Recent Documents
            </h2>
            <BrandedCard hoverable={false}>
              {docsLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-6 w-full" />
                  ))}
                </div>
              ) : recentDocs === null ? (
                <div className="flex items-center gap-3 py-4">
                  <FileText
                    className="size-5 shrink-0"
                    style={{ color: colors.secondaryText }}
                  />
                  <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
                    Documents coming soon
                  </p>
                </div>
              ) : recentDocs.length === 0 ? (
                <div className="flex items-center gap-3 py-4">
                  <FileText
                    className="size-5 shrink-0"
                    style={{ color: colors.secondaryText }}
                  />
                  <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
                    No documents yet. They'll appear here as you use Flywheel.
                  </p>
                </div>
              ) : (
                <div className="divide-y" style={{ borderColor: colors.subtleBorder }}>
                  {recentDocs.map((doc) => (
                    <Link
                      key={doc.id}
                      to={`/documents/${doc.id}`}
                      className="flex items-center gap-3 py-3 first:pt-0 last:pb-0 no-underline hover:opacity-80 transition-opacity"
                    >
                      {doc.doc_type === 'company_intel' ? (
                        <Building2 className="size-4 shrink-0" style={{ color: colors.brandCoral }} />
                      ) : (
                        <FileText className="size-4 shrink-0" style={{ color: colors.brandCoral }} />
                      )}
                      <span
                        className="truncate flex-1"
                        style={{
                          fontSize: typography.body.size,
                          color: colors.headingText,
                        }}
                      >
                        {doc.title}
                      </span>
                      <span
                        className="shrink-0 flex items-center gap-1"
                        style={{
                          fontSize: typography.caption.size,
                          color: colors.secondaryText,
                        }}
                      >
                        <Clock className="size-3" />
                        {formatRelativeTime(doc.created_at)}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
              <div className="mt-3 pt-3 border-t" style={{ borderColor: colors.subtleBorder }}>
                <Link
                  to="/documents"
                  className="text-sm no-underline hover:underline"
                  style={{ color: 'var(--brand-coral)' }}
                >
                  View all docs &rarr;
                </Link>
              </div>
            </BrandedCard>
          </div>

          {/* Suggested Actions (cards from briefing API) */}
          {isLoading ? (
            <div style={{ marginBottom: spacing.section }}>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-32 rounded-xl" />
                ))}
              </div>
            </div>
          ) : data?.cards && data.cards.length > 0 ? (
            <div style={{ marginBottom: spacing.section }}>
              <h2
                style={{
                  fontSize: typography.sectionTitle.size,
                  fontWeight: typography.sectionTitle.weight,
                  lineHeight: typography.sectionTitle.lineHeight,
                  color: colors.headingText,
                  marginBottom: spacing.element,
                }}
              >
                Suggested Actions
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {data.cards.map((card, i) => {
                  if (card.card_type === 'personal_gap') {
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
            </div>
          ) : !isLoading && streams.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <InboxIcon className="mb-4 h-12 w-12 text-muted-foreground/50" />
              <h2
                style={{
                  fontSize: typography.sectionTitle.size,
                  fontWeight: typography.sectionTitle.weight,
                  color: colors.headingText,
                }}
              >
                Your workspace is ready
              </h2>
              <p
                className="mt-1 max-w-sm"
                style={{
                  fontSize: typography.body.size,
                  color: colors.secondaryText,
                }}
              >
                Start by creating a focus area to organize your knowledge around
                the projects and accounts that matter most.
              </p>
              <Link
                to="/streams/new"
                className="mt-4 text-sm no-underline hover:underline"
                style={{ color: 'var(--brand-coral)' }}
              >
                Create a focus area
              </Link>
            </div>
          ) : null}
        </div>
      </div>

      {/* Global Chat Input - pinned at bottom */}
      <div className="border-t bg-background p-4">
        <GlobalChatInput />
      </div>
    </div>
  )
}
