import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router'
import { useAccounts } from '../hooks/useAccounts'
import type { AccountListParams, AccountStatus, FitTier } from '../types/accounts'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { spacing, typography } from '@/lib/design-tokens'

const PAGE_SIZE = 20

const STATUS_COLORS: Record<AccountStatus, string> = {
  prospect: 'bg-blue-100 text-blue-700',
  engaged: 'bg-[#FDE8E4] text-[#E94D35]',
  customer: 'bg-green-100 text-green-700',
  churned: 'bg-gray-100 text-gray-500',
  disqualified: 'bg-red-100 text-red-700',
}

const FIT_TIER_COLORS: Record<FitTier, string> = {
  excellent: 'bg-green-100 text-green-700',
  good: 'bg-blue-100 text-blue-700',
  fair: 'bg-amber-100 text-amber-700',
  poor: 'bg-gray-100 text-gray-500',
}

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'prospect', label: 'Prospect' },
  { value: 'engaged', label: 'Engaged' },
  { value: 'customer', label: 'Customer' },
  { value: 'churned', label: 'Churned' },
  { value: 'disqualified', label: 'Disqualified' },
]

type SortableColumn = 'name' | 'fit_score' | 'last_interaction_at' | 'next_action_due'

const SORTABLE_COLUMNS: SortableColumn[] = ['name', 'fit_score', 'last_interaction_at', 'next_action_due']

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'Never'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMs < 0) {
    // Future date
    const absDays = Math.abs(diffDays)
    const absHours = Math.abs(diffHours)
    if (absDays > 0) return `in ${absDays}d`
    if (absHours > 0) return `in ${absHours}h`
    return 'soon'
  }
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  const diffMonths = Math.floor(diffDays / 30)
  return `${diffMonths}mo ago`
}

function isOverdue(isoString: string | null): boolean {
  if (!isoString) return false
  return new Date(isoString) < new Date()
}

export function AccountsPage() {
  const navigate = useNavigate()

  // State for filters
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState<string>('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [offset, setOffset] = useState(0)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput)
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const params: AccountListParams = useMemo(
    () => ({
      offset,
      limit: PAGE_SIZE,
      status: statusFilter || undefined,
      search: debouncedSearch || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [offset, statusFilter, debouncedSearch, sortBy, sortDir],
  )

  const { data, isLoading, isError, error, refetch } = useAccounts(params)

  function handleSort(column: string) {
    if (sortBy === column) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(column)
      setSortDir('asc')
    }
    setOffset(0)
  }

  function handleStatusChange(value: string) {
    setStatusFilter(value)
    setOffset(0)
  }

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const showingStart = total === 0 ? 0 : offset + 1
  const showingEnd = Math.min(offset + PAGE_SIZE, total)

  function renderSortIndicator(column: string) {
    if (sortBy !== column) return null
    return <span className="ml-1 text-xs">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>
  }

  // Loading skeleton
  if (isLoading && !data) {
    return (
      <div className="mx-auto w-full" style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}>
        <h1 style={{ fontSize: typography.pageTitle.size, fontWeight: typography.pageTitle.weight, lineHeight: typography.pageTitle.lineHeight, letterSpacing: typography.pageTitle.letterSpacing }} className="text-foreground">
          Accounts
        </h1>
        <div className="mt-6 flex items-center gap-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-8 w-40" />
        </div>
        <div className="mt-4 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="mx-auto w-full" style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}>
        <h1 style={{ fontSize: typography.pageTitle.size, fontWeight: typography.pageTitle.weight, lineHeight: typography.pageTitle.lineHeight, letterSpacing: typography.pageTitle.letterSpacing }} className="text-foreground">
          Accounts
        </h1>
        <div className="mt-8 flex flex-col items-center gap-4">
          <p className="text-muted-foreground">Failed to load accounts: {(error as Error)?.message ?? 'Unknown error'}</p>
          <Button variant="outline" onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full" style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}>
      {/* Page title */}
      <h1 style={{ fontSize: typography.pageTitle.size, fontWeight: typography.pageTitle.weight, lineHeight: typography.pageTitle.lineHeight, letterSpacing: typography.pageTitle.letterSpacing }} className="text-foreground">
        Accounts
      </h1>

      {/* Search and filter bar */}
      <div className="mt-6 flex items-center gap-3">
        <Input
          placeholder="Search accounts..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={statusFilter}
          onChange={(e) => handleStatusChange(e.target.value)}
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr className="border-b border-border text-sm text-muted-foreground">
              {[
                { key: 'name', label: 'Name' },
                { key: 'status', label: 'Status' },
                { key: 'fit_score', label: 'Fit Score' },
                { key: 'contacts', label: 'Contacts' },
                { key: 'last_interaction_at', label: 'Last Interaction' },
                { key: 'next_action_due', label: 'Next Action' },
              ].map((col) => {
                const isSortable = SORTABLE_COLUMNS.includes(col.key as SortableColumn)
                return (
                  <th
                    key={col.key}
                    className={`px-3 py-2 font-medium ${isSortable ? 'cursor-pointer select-none hover:text-foreground' : ''}`}
                    onClick={isSortable ? () => handleSort(col.key) : undefined}
                  >
                    {col.label}
                    {isSortable && renderSortIndicator(col.key)}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-16 text-center text-muted-foreground">
                  No accounts found
                </td>
              </tr>
            ) : (
              items.map((account) => (
                <tr
                  key={account.id}
                  onClick={() => navigate(`/accounts/${account.id}`)}
                  className="cursor-pointer border-b border-border/50 transition-colors hover:bg-muted/50"
                >
                  {/* Name */}
                  <td className="px-3 py-3">
                    <div className="font-medium text-foreground">{account.name}</div>
                    {account.domain && (
                      <div style={{ fontSize: typography.caption.size }} className="text-muted-foreground">{account.domain}</div>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-3 py-3">
                    <Badge className={`${STATUS_COLORS[account.status] ?? 'bg-gray-100 text-gray-700'} border-0 text-xs font-medium`}>
                      {account.status}
                    </Badge>
                  </td>

                  {/* Fit Score */}
                  <td className="px-3 py-3">
                    {account.fit_tier ? (
                      <span className="flex items-center gap-1.5">
                        <Badge className={`${FIT_TIER_COLORS[account.fit_tier] ?? 'bg-gray-100 text-gray-500'} border-0 text-xs font-medium`}>
                          {account.fit_tier}
                        </Badge>
                        {account.fit_score !== null && (
                          <span className="text-sm text-muted-foreground">{account.fit_score}</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </td>

                  {/* Contacts */}
                  <td className="px-3 py-3 text-sm text-foreground">{account.contact_count}</td>

                  {/* Last Interaction */}
                  <td className="px-3 py-3 text-sm text-muted-foreground">
                    {formatRelativeTime(account.last_interaction_at)}
                  </td>

                  {/* Next Action */}
                  <td className="px-3 py-3">
                    {account.next_action_due ? (
                      <span className="flex items-center gap-1.5">
                        <span
                          className="text-sm"
                          style={{ color: isOverdue(account.next_action_due) ? '#F59E0B' : undefined }}
                        >
                          {formatRelativeTime(account.next_action_due)}
                        </span>
                        {account.next_action_type && (
                          <Badge className="border-0 bg-gray-100 text-xs font-medium text-gray-600">
                            {account.next_action_type}
                          </Badge>
                        )}
                      </span>
                    ) : (
                      <span className="text-sm text-muted-foreground">None</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {total > 0 ? `Showing ${showingStart}-${showingEnd} of ${total} accounts` : 'No accounts'}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={!data?.has_more}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
