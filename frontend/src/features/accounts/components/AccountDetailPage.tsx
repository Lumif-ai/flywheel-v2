import { useParams, Link } from 'react-router'
import { spacing, typography } from '@/lib/design-tokens'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, Globe } from 'lucide-react'
import { useAccountDetail } from '../hooks/useAccountDetail'
import { ContactsPanel } from './ContactsPanel'
import { TimelineFeed } from './TimelineFeed'
import { IntelSidebar } from './IntelSidebar'
import { ActionBar } from './ActionBar'
import type { AccountStatus, FitTier } from '../types/accounts'

function statusVariant(status: AccountStatus) {
  switch (status) {
    case 'customer':
      return 'default' as const
    case 'engaged':
      return 'secondary' as const
    case 'prospect':
      return 'outline' as const
    case 'churned':
    case 'disqualified':
      return 'destructive' as const
    default:
      return 'outline' as const
  }
}

function fitTierColor(tier: FitTier | null): string {
  switch (tier) {
    case 'excellent':
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
    case 'good':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
    case 'fair':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
    case 'poor':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
    default:
      return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
  }
}

function DetailSkeleton() {
  return (
    <div
      className="mx-auto w-full"
      style={{
        maxWidth: spacing.maxGrid,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      <Skeleton className="h-5 w-24 mb-6" />
      <Skeleton className="h-8 w-64 mb-2" />
      <Skeleton className="h-5 w-48 mb-8" />
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_300px] gap-6">
        <div className="space-y-3">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    </div>
  )
}

export function AccountDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: account, isLoading, error } = useAccountDetail(id ?? '')

  if (isLoading) {
    return <DetailSkeleton />
  }

  if (error || !account) {
    return (
      <div
        className="mx-auto w-full"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        <Link
          to="/accounts"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="size-4" />
          Accounts
        </Link>
        <h1
          className="text-foreground"
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
          }}
        >
          Account not found
        </h1>
        <p className="mt-2 text-muted-foreground">
          This account may have been removed or you don't have access.
        </p>
      </div>
    )
  }

  return (
    <div
      className="mx-auto w-full"
      style={{
        maxWidth: spacing.maxGrid,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      {/* Back link */}
      <Link
        to="/accounts"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
      >
        <ArrowLeft className="size-4" />
        Accounts
      </Link>

      {/* Company header */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <h1
            className="text-foreground"
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
            }}
          >
            {account.name}
          </h1>
          <Badge variant={statusVariant(account.status)}>{account.status}</Badge>
          {account.fit_tier && (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${fitTierColor(account.fit_tier)}`}
            >
              {account.fit_score != null && `${account.fit_score} -- `}
              {account.fit_tier}
            </span>
          )}
        </div>
        {account.domain && (
          <a
            href={`https://${account.domain}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            <Globe className="size-3.5" />
            {account.domain}
          </a>
        )}
      </div>

      {/* 3-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_300px] gap-6">
        <div>
          <ContactsPanel contacts={account.contacts} />
        </div>
        <div>
          <TimelineFeed
            accountId={account.id}
            initialTimeline={account.recent_timeline}
          />
        </div>
        <div>
          <IntelSidebar intel={account.intel} />
        </div>
      </div>

      {/* Action bar */}
      <ActionBar accountId={account.id} accountName={account.name} />
    </div>
  )
}
