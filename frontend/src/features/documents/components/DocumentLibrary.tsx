import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { Toast } from '@/components/ui/toast-notification'
import { DocumentCard } from './DocumentCard'
import { fetchDocuments, shareDocument } from '../api'
import type { DocumentListItem } from '../api'

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

type FilterType = 'all' | 'meeting-prep' | 'company-intel'

const FILTERS: { key: FilterType; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'meeting-prep', label: 'Meeting Preps' },
  { key: 'company-intel', label: 'Company Intel' },
]

// ---------------------------------------------------------------------------
// Date grouping
// ---------------------------------------------------------------------------

function getDateGroup(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86_400_000)
  const weekAgo = new Date(today.getTime() - 7 * 86_400_000)

  if (date >= today) return 'TODAY'
  if (date >= yesterday) return 'YESTERDAY'
  if (date >= weekAgo) return 'THIS WEEK'
  return 'EARLIER'
}

function groupByDate(docs: DocumentListItem[]): Map<string, DocumentListItem[]> {
  const groups = new Map<string, DocumentListItem[]>()
  const order = ['TODAY', 'YESTERDAY', 'THIS WEEK', 'EARLIER']
  for (const key of order) groups.set(key, [])
  for (const doc of docs) {
    const group = getDateGroup(doc.created_at)
    groups.get(group)!.push(doc)
  }
  // Remove empty groups
  for (const [key, value] of groups) {
    if (value.length === 0) groups.delete(key)
  }
  return groups
}

// ---------------------------------------------------------------------------
// Skeleton loader
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-xl shadow-sm p-6">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg animate-shimmer bg-[var(--skeleton-bg)]" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
          <div className="h-3 w-1/2 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <div className="h-8 w-16 rounded-lg animate-shimmer bg-[var(--skeleton-bg)]" />
        <div className="h-8 w-16 rounded-lg animate-shimmer bg-[var(--skeleton-bg)]" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state illustration
// ---------------------------------------------------------------------------

function EmptyDocumentsIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Stacked document pages */}
      <rect x="18" y="12" width="44" height="56" rx="4" fill="var(--card-bg)" stroke="var(--subtle-border)" strokeWidth="1.5" />
      <rect x="14" y="16" width="44" height="56" rx="4" fill="var(--card-bg)" stroke="var(--subtle-border)" strokeWidth="1.5" />
      <rect x="10" y="20" width="44" height="56" rx="4" fill="var(--card-bg)" stroke="var(--brand-coral)" strokeWidth="1.5" opacity="0.9" />
      {/* Content lines on front page */}
      <rect x="18" y="30" width="24" height="2" rx="1" fill="var(--brand-coral)" opacity="0.4" />
      <rect x="18" y="36" width="28" height="2" rx="1" fill="var(--subtle-border)" />
      <rect x="18" y="42" width="20" height="2" rx="1" fill="var(--subtle-border)" />
      <rect x="18" y="48" width="26" height="2" rx="1" fill="var(--subtle-border)" />
      <rect x="18" y="56" width="16" height="2" rx="1" fill="var(--brand-coral)" opacity="0.3" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20

export function DocumentLibrary() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [filter, setFilter] = useState<FilterType>('all')
  const [extraPages, setExtraPages] = useState<DocumentListItem[]>([])
  const [shareToast, setShareToast] = useState<string | null>(null)

  const queryParams = {
    limit: PAGE_SIZE,
    offset: 0,
    ...(filter !== 'all' ? { document_type: filter } : {}),
  }

  const { data, isLoading: loading } = useQuery({
    queryKey: ['documents', filter],
    queryFn: () => fetchDocuments(queryParams),
    enabled: !!user,
  })

  const firstPageDocs = data?.documents ?? []
  const total = data?.total ?? 0
  const documents = [...firstPageDocs, ...extraPages]

  const handleFilterChange = (f: FilterType) => {
    setFilter(f)
    setExtraPages([])
  }

  const handleLoadMore = async () => {
    const newOffset = documents.length
    try {
      const params = { limit: PAGE_SIZE, offset: newOffset, ...(filter !== 'all' ? { document_type: filter } : {}) }
      const res = await fetchDocuments(params)
      setExtraPages((prev) => [...prev, ...res.documents])
    } catch (err) {
      console.error('Failed to load more documents:', err)
    }
  }

  const handleShare = async (doc: DocumentListItem) => {
    try {
      const res = await shareDocument(doc.id)
      const url = `${window.location.origin}${res.share_url}`
      await navigator.clipboard.writeText(url)
      setShareToast(url)
    } catch (err) {
      console.error('Failed to share document:', err)
    }
  }

  const handleView = (doc: DocumentListItem) => {
    navigate(`/documents/${doc.id}`)
  }

  const grouped = groupByDate(documents)
  const hasMore = documents.length < total

  return (
    <div
      className="mx-auto w-full page-enter"
      style={{
        maxWidth: spacing.maxGrid,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      <Toast message="Link copied to clipboard" visible={!!shareToast} onDismiss={() => setShareToast(null)} />

      {/* Page title */}
      <h1
        style={{
          fontSize: typography.pageTitle.size,
          fontWeight: typography.pageTitle.weight,
          lineHeight: typography.pageTitle.lineHeight,
          letterSpacing: typography.pageTitle.letterSpacing,
          color: colors.headingText,
          marginBottom: spacing.card,
        }}
      >
        Library
      </h1>

      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-8">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => handleFilterChange(f.key)}
            className="px-4 py-2 rounded-full text-sm font-medium transition-all duration-200"
            style={
              filter === f.key
                ? {
                    background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
                    color: '#fff',
                  }
                : {
                    backgroundColor: colors.brandTint,
                    color: colors.secondaryText,
                  }
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Loading skeleton */}
      {loading && documents.length === 0 && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {/* Empty state */}
      {!loading && documents.length === 0 && (
        <div className="text-center py-16 rounded-xl" style={{ backgroundColor: 'rgba(233,77,53,0.03)' }}>
          <div className="flex justify-center mb-4">
            <EmptyDocumentsIllustration />
          </div>
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
            Your intelligence library grows with every skill you run
          </p>
          <p className="mt-1" style={{ fontSize: typography.caption.size, color: colors.secondaryText, opacity: 0.7 }}>
            Briefings, research, and analysis — all saved here
          </p>
        </div>
      )}

      {/* Document timeline grouped by date */}
      {!loading || documents.length > 0
        ? Array.from(grouped.entries()).map(([group, docs]) => (
            <div key={group} className="mb-8">
              <h2
                className="uppercase tracking-wider mb-4"
                style={{
                  fontSize: typography.caption.size,
                  fontWeight: '600',
                  color: colors.secondaryText,
                  letterSpacing: '0.05em',
                }}
              >
                {group}
              </h2>
              <div className="space-y-3">
                {docs.map((doc, i) => (
                  <DocumentCard
                    key={doc.id}
                    document={doc}
                    index={i}
                    onShare={handleShare}
                    onView={handleView}
                  />
                ))}
              </div>
            </div>
          ))
        : null}

      {/* Load more */}
      {hasMore && !loading && (
        <div className="flex justify-center mt-8">
          <button
            type="button"
            onClick={handleLoadMore}
            className="px-6 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 hover:shadow-md"
            style={{
              backgroundColor: colors.brandTint,
              color: colors.brandCoral,
            }}
          >
            Load more
          </button>
        </div>
      )}

      {/* Loading more indicator */}
      {loading && documents.length > 0 && (
        <div className="flex justify-center mt-4">
          <div className="w-6 h-6 border-2 border-[var(--subtle-border)] border-t-[var(--brand-coral)] rounded-full animate-spin" />
        </div>
      )}
    </div>
  )
}
