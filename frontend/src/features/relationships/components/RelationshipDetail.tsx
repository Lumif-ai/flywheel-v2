import { useParams, useSearchParams, Link } from 'react-router'
import { ArrowLeft } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { spacing, registers } from '@/lib/design-tokens'
import { useRelationshipDetail } from '../hooks/useRelationshipDetail'
import { RelationshipHeader } from './RelationshipHeader'
import { AskPanel } from './AskPanel'
import type { RelationshipType } from '../types/relationships'

// TAB_CONFIG drives all tab rendering — single source of truth
// Prospects and Customers include Intelligence tab; Advisors and Investors do not
const TAB_CONFIG: Record<RelationshipType, Array<{ key: string; label: string }>> = {
  prospect: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'commitments', label: 'Commitments' },
  ],
  customer: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'commitments', label: 'Commitments' },
  ],
  advisor: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'commitments', label: 'Commitments' },
  ],
  investor: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'commitments', label: 'Commitments' },
  ],
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

function DetailSkeleton() {
  return (
    <div
      className="min-h-dvh"
      style={{ background: registers.relationship.background }}
    >
      <div
        className="mx-auto w-full"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        {/* Back link skeleton */}
        <Skeleton className="h-4 w-24 mb-6" />

        {/* Header skeleton */}
        <div className="flex items-start gap-4 mb-6">
          <Skeleton className="size-12 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          </div>
        </div>

        {/* Two-panel skeleton */}
        <div className="flex flex-col lg:flex-row gap-6 mt-6">
          {/* Left AI panel skeleton */}
          <div className="w-full lg:w-[320px] lg:shrink-0">
            <Skeleton className="h-[400px] w-full rounded-xl" />
          </div>
          {/* Right panel skeleton */}
          <div className="flex-1 min-w-0 space-y-4">
            <div className="flex gap-3">
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-28" />
            </div>
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

export function RelationshipDetail() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()

  // CRITICAL: Always derive type from URL param, NOT from account.relationship_type
  // (account may belong to multiple types — fromType is the entry-point context)
  const fromType = (searchParams.get('fromType') as RelationshipType) ?? 'prospect'
  const backPath = `/relationships/${fromType}s`
  const backLabel = capitalize(`${fromType}s`)

  const { data: account, isLoading, error } = useRelationshipDetail(id ?? '')

  if (isLoading) {
    return <DetailSkeleton />
  }

  if (error || !account) {
    return (
      <div
        className="min-h-dvh"
        style={{ background: registers.relationship.background }}
      >
        <div
          className="mx-auto w-full"
          style={{
            maxWidth: spacing.maxGrid,
            padding: `${spacing.section} ${spacing.pageDesktop}`,
          }}
        >
          <Link
            to={backPath}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
          >
            <ArrowLeft className="size-4" />
            {backLabel}
          </Link>
          <h1 className="text-foreground text-xl font-semibold">
            Relationship not found
          </h1>
          <p className="mt-2 text-muted-foreground text-sm">
            This relationship may have been removed or you don&apos;t have access.
          </p>
        </div>
      </div>
    )
  }

  const tabs = TAB_CONFIG[fromType]

  return (
    <div
      className="min-h-dvh"
      style={{ background: registers.relationship.background }}
    >
      <div
        className="mx-auto w-full"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        {/* Back link */}
        <Link
          to={backPath}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="size-4" />
          {backLabel}
        </Link>

        {/* Header: avatar, name, domain, type badges, entity level, status */}
        <RelationshipHeader account={account} fromType={fromType} />

        {/* Two-panel layout */}
        <div className="flex flex-col lg:flex-row gap-6 mt-6">
          {/* Left panel: 320px AI context panel */}
          <div className="w-full lg:w-[320px] lg:shrink-0">
            <AskPanel
              accountId={account.id}
              aiSummary={account.ai_summary}
              aiSummaryUpdatedAt={account.ai_summary_updated_at}
            />
          </div>

          {/* Right panel: header + type-driven tabs */}
          <div className="flex-1 min-w-0">
            <Tabs defaultValue="timeline">
              <TabsList variant="line" className="w-full justify-start border-b border-border mb-4">
                {tabs.map((tab) => (
                  <TabsTrigger key={tab.key} value={tab.key}>
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              {tabs.map((tab) => (
                <TabsContent key={tab.key} value={tab.key}>
                  {/* Plan 04 replaces these placeholders with real tab components */}
                  <div className="py-4 text-muted-foreground text-sm">
                    Coming soon...
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  )
}
