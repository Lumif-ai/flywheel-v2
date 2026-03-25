import { useMemo, useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useBriefing } from '../hooks/useBriefing'
import { useStreams } from '../hooks/useStreams'
import { BriefingCard } from './BriefingCard'
import { PersonalGapCard } from './PersonalGapCard'
import { NudgeCard } from './NudgeCard'
import { KnowledgeHealthBar } from './KnowledgeHealthBar'
import { GlobalChatInput } from './GlobalChatInput'
import { NextActionCta } from './NextActionCta'
import { StreamDensityCard } from '@/features/streams/components/DensityIndicator'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { Link } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { FileText, Building2, Clock } from 'lucide-react'
import { api } from '@/lib/api'
import { spacing, typography, colors } from '@/lib/design-tokens'

function EmptyWorkspaceIllustration() {
  return (
    <svg width="120" height="80" viewBox="0 0 120 80" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Three connected circles representing knowledge nodes */}
      <line x1="30" y1="40" x2="60" y2="25" stroke="var(--subtle-border)" strokeWidth="2" />
      <line x1="60" y1="25" x2="90" y2="40" stroke="var(--subtle-border)" strokeWidth="2" />
      <line x1="30" y1="40" x2="90" y2="40" stroke="var(--subtle-border)" strokeWidth="2" strokeDasharray="4 4" />
      <circle cx="30" cy="40" r="12" fill="var(--brand-tint)" stroke="var(--brand-coral)" strokeWidth="1.5" />
      <circle cx="60" cy="25" r="10" fill="var(--brand-tint)" stroke="var(--brand-coral)" strokeWidth="1.5" opacity="0.7" />
      <circle cx="90" cy="40" r="14" fill="var(--brand-tint)" stroke="var(--brand-coral)" strokeWidth="1.5" />
      {/* Small dots for detail */}
      <circle cx="30" cy="40" r="3" fill="var(--brand-coral)" />
      <circle cx="60" cy="25" r="2.5" fill="var(--brand-coral)" opacity="0.7" />
      <circle cx="90" cy="40" r="3.5" fill="var(--brand-coral)" />
    </svg>
  )
}

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
  const navigate = useNavigate()
  const { data, isLoading, error } = useBriefing()
  const { data: streamsData } = useStreams()
  const user = useAuthStore(state => state.user)
  const { state: lifecycleState } = useLifecycleState()

  const [recentDocs, setRecentDocs] = useState<RecentDocument[] | null>(null)
  const [docsLoading, setDocsLoading] = useState(true)

  const streams = streamsData?.items ?? []

  const isFirstVisitLifecycle = lifecycleState === 'S1' || lifecycleState === 'S2'

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

  const isFirstVisit = isFirstVisitLifecycle && !isLoading

  // Redirect unonboarded users to onboarding
  // No onboarding intel + no streams = user hasn't set up their company
  const hasNoData = !isLoading && data && !data.is_first_visit
    && (data.knowledge_health?.total_entries ?? 0) === 0
    && streams.length === 0
  useEffect(() => {
    if (hasNoData) {
      navigate('/onboarding', { replace: true })
    }
  }, [hasNoData, navigate])

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
          {/* ----------------------------------------------------------------
              FIRST-VISIT LAYOUT
              Show hero content (briefing or intel summary) + next action CTA.
              Suppress conversion CTAs, empty sections, and health metrics.
          ----------------------------------------------------------------- */}
          {isFirstVisit ? (
            <div style={{ maxWidth: '720px', margin: '0 auto', width: '100%' }}>
              {/* Greeting */}
              <div style={{ marginBottom: spacing.section }}>
                <h1
                  style={{
                    fontSize: typography.pageTitle.size,
                    fontWeight: typography.pageTitle.weight,
                    lineHeight: typography.pageTitle.lineHeight,
                    letterSpacing: typography.pageTitle.letterSpacing,
                    color: colors.headingText,
                    marginBottom: '4px',
                  }}
                >
                  Welcome to your workspace{userName ? `, ${userName}` : ''}.
                </h1>
                <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
                  Your first briefing is in your Library. Every meeting makes your workspace smarter.
                </p>
              </div>

              {/* Library section -- shows onboarding briefing as clickable item */}
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
                  Library
                  {recentDocs && recentDocs.length > 0 && (
                    <span
                      style={{
                        fontSize: typography.caption.size,
                        fontWeight: '400',
                        color: colors.secondaryText,
                        marginLeft: '8px',
                      }}
                    >
                      ({recentDocs.length} {recentDocs.length === 1 ? 'item' : 'items'})
                    </span>
                  )}
                </h2>
                <BrandedCard hoverable={false}>
                  {docsLoading ? (
                    <div className="space-y-3">
                      {Array.from({ length: 2 }).map((_, i) => (
                        <Skeleton key={i} className="h-6 w-full" />
                      ))}
                    </div>
                  ) : recentDocs && recentDocs.length > 0 ? (
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
                  ) : (
                    <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
                      Your briefings and research will appear here.
                    </p>
                  )}
                  <div className="mt-3 pt-3 border-t" style={{ borderColor: colors.subtleBorder }}>
                    <Link
                      to="/documents"
                      className="text-sm no-underline hover:underline"
                      style={{ color: 'var(--brand-coral)' }}
                    >
                      View all in Library &rarr;
                    </Link>
                  </div>
                </BrandedCard>
              </div>

              {/* Focus areas if available */}
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
                  <div className="grid gap-4 md:grid-cols-2">
                    {streams.filter(s => !s.is_archived).map((stream) => (
                      <Link key={stream.id} to={`/streams/${stream.id}`} className="block no-underline">
                        <BrandedCard variant="info">
                          <p
                            className="truncate"
                            style={{
                              fontSize: typography.body.size,
                              fontWeight: '500',
                              color: colors.headingText,
                              margin: 0,
                            }}
                          >
                            {stream.name}
                          </p>
                        </BrandedCard>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* Next action CTA if available */}
              {data?.first_visit?.primary_priority && (
                <div style={{ marginBottom: spacing.section }}>
                  <NextActionCta primaryPriority={data.first_visit.primary_priority} />
                </div>
              )}
            </div>
          ) : (
            /* ----------------------------------------------------------------
               NORMAL DASHBOARD LAYOUT (returning users)
            ----------------------------------------------------------------- */
            <>
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
                    <div className="flex flex-col items-center gap-2 py-6">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-8 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.3 }} />
                        <div className="h-1.5 w-12 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.2 }} />
                        <div className="h-1.5 w-6 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.15 }} />
                      </div>
                      <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                        Your briefings and research will appear here
                      </p>
                    </div>
                  ) : recentDocs.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 py-6">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-8 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.3 }} />
                        <div className="h-1.5 w-12 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.2 }} />
                        <div className="h-1.5 w-6 rounded-full" style={{ backgroundColor: 'var(--brand-coral)', opacity: 0.15 }} />
                      </div>
                      <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                        Your briefings and research will appear here
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
                <div
                  className="flex flex-col items-center justify-center text-center"
                  style={{ backgroundColor: 'rgba(233,77,53,0.02)', borderRadius: '16px', padding: '48px 24px' }}
                >
                  <EmptyWorkspaceIllustration />
                  <h2
                    className="mt-5"
                    style={{
                      fontSize: typography.sectionTitle.size,
                      fontWeight: typography.sectionTitle.weight,
                      color: colors.headingText,
                    }}
                  >
                    Build your knowledge graph
                  </h2>
                  <p
                    className="mt-1 max-w-sm"
                    style={{
                      fontSize: typography.body.size,
                      color: colors.secondaryText,
                    }}
                  >
                    Create a focus area for each project, account, or initiative
                    you&apos;re working on. Flywheel compounds everything you learn.
                  </p>
                  <Link
                    to="/streams/new"
                    className="mt-5 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium no-underline transition-all duration-200 hover:shadow-md hover:-translate-y-px"
                    style={{
                      background: `linear-gradient(135deg, var(--brand-coral), var(--brand-gradient-end))`,
                      color: '#fff',
                    }}
                  >
                    Create your first focus area
                  </Link>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      {/* Global Chat Input - pinned at bottom */}
      <div className="border-t bg-background p-4">
        <GlobalChatInput
          placeholder={isFirstVisit ? 'What would you like to research next?' : undefined}
        />
      </div>
    </div>
  )
}
