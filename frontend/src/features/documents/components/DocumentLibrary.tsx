import { useState, useMemo, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Search, X, FileText } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { Toast } from '@/components/ui/toast-notification'
import { EmptyState } from '@/components/ui/empty-state'
import { ViewToggle, type ViewMode } from '@/components/ui/view-toggle'
import { DocumentRow, DocumentRowSkeleton } from './DocumentRow'
import { DocumentGridCard, DocumentGridCardSkeleton } from './DocumentGridCard'
import { fetchDocuments, shareDocument } from '../api'
import type { DocumentListItem } from '../api'
import { getTypeStyle } from '../utils'

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
  for (const [key, value] of groups) {
    if (value.length === 0) groups.delete(key)
  }
  return groups
}

// ---------------------------------------------------------------------------
// View mode persistence
// ---------------------------------------------------------------------------

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem('library-view-mode')
    if (stored === 'grid' || stored === 'list') return stored
  } catch {
    // ignore
  }
  return 'list'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50

export function DocumentLibrary() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [activeTab, setActiveTab] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode)
  const [extraPages, setExtraPages] = useState<DocumentListItem[]>([])
  const [shareToast, setShareToast] = useState<string | null>(null)

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Persist view mode
  const handleViewChange = useCallback((mode: ViewMode) => {
    setViewMode(mode)
    try { localStorage.setItem('library-view-mode', mode) } catch { /* ignore */ }
  }, [])

  // Fetch all documents
  const { data, isLoading: loading } = useQuery({
    queryKey: ['documents', 'all'],
    queryFn: () => fetchDocuments({ limit: PAGE_SIZE, offset: 0 }),
    enabled: !!user,
  })

  const firstPageDocs = data?.documents ?? []
  const total = data?.total ?? 0
  const allDocuments = [...firstPageDocs, ...extraPages]

  // Build tabs dynamically from document types
  const tabs = useMemo(() => {
    const typeCounts = new Map<string, number>()
    for (const doc of allDocuments) {
      typeCounts.set(doc.document_type, (typeCounts.get(doc.document_type) ?? 0) + 1)
    }
    // Sort by count descending
    const typeEntries = Array.from(typeCounts.entries()).sort((a, b) => b[1] - a[1])
    return [
      { key: 'all', label: 'All', count: allDocuments.length },
      ...typeEntries.map(([type, count]) => ({
        key: type,
        label: getTypeStyle(type).label,
        count,
      })),
    ]
  }, [allDocuments])

  // Filter by active tab
  const tabFiltered = useMemo(() => {
    if (activeTab === 'all') return allDocuments
    return allDocuments.filter((doc) => doc.document_type === activeTab)
  }, [allDocuments, activeTab])

  // Apply search on top of tab filter
  const documents = useMemo(() => {
    if (!debouncedSearch.trim()) return tabFiltered
    const q = debouncedSearch.toLowerCase()
    return tabFiltered.filter((doc) => {
      const title = doc.title.toLowerCase()
      const companies = (doc.metadata?.companies ?? []).join(' ').toLowerCase()
      const contacts = (doc.metadata?.contacts ?? []).join(' ').toLowerCase()
      return title.includes(q) || companies.includes(q) || contacts.includes(q)
    })
  }, [tabFiltered, debouncedSearch])

  const handleLoadMore = async () => {
    const newOffset = allDocuments.length
    try {
      const res = await fetchDocuments({ limit: PAGE_SIZE, offset: newOffset })
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

  const handleClearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
  }

  const grouped = groupByDate(documents)
  const hasMore = allDocuments.length < total && !debouncedSearch.trim()

  return (
    <div
      className="mx-auto w-full page-enter"
      style={{
        maxWidth: spacing.maxGrid,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      <Toast message="Link copied to clipboard" visible={!!shareToast} onDismiss={() => setShareToast(null)} />

      {/* ── Header ── */}
      <div className="flex items-baseline gap-3 mb-2">
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            letterSpacing: typography.pageTitle.letterSpacing,
            color: colors.headingText,
          }}
        >
          Library
        </h1>
        {total > 0 && (
          <span
            className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium"
            style={{
              fontSize: typography.caption.size,
              backgroundColor: colors.brandTint,
              color: colors.secondaryText,
            }}
          >
            {total}
          </span>
        )}
      </div>

      {/* ── Tabs ── */}
      <div
        className="flex items-center gap-1 overflow-x-auto mb-6 -mx-1 px-1"
        role="tablist"
        aria-label="Document types"
        style={{ borderBottom: `1px solid ${colors.subtleBorder}` }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.key)}
              className="relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors duration-200"
              style={{
                color: isActive ? colors.headingText : colors.secondaryText,
              }}
            >
              {tab.label}
              <span
                className="text-xs tabular-nums rounded-full px-1.5 py-0.5"
                style={{
                  backgroundColor: isActive ? colors.brandTint : 'transparent',
                  color: isActive ? 'var(--brand-coral)' : colors.secondaryText,
                  opacity: isActive ? 1 : 0.6,
                }}
              >
                {tab.count}
              </span>
              {/* Active indicator bar */}
              {isActive && (
                <span
                  className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                  style={{ backgroundColor: 'var(--brand-coral)' }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* ── Search + View toggle ── */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-sm" role="search">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: colors.secondaryText }}
            aria-hidden="true"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents..."
            aria-label="Search documents"
            className="w-full h-10 pl-9 pr-9 rounded-xl border border-[var(--subtle-border)] bg-[var(--card-bg)] text-sm transition-all duration-200 outline-none focus:border-[var(--brand-coral)] focus:ring-2 focus:ring-[rgba(233,77,53,0.15)]"
            style={{ color: colors.headingText }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={handleClearSearch}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 inline-flex items-center justify-center size-6 rounded-md transition-colors hover:bg-[var(--brand-tint)]"
              style={{ color: colors.secondaryText }}
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>
        <div className="ml-auto">
          <ViewToggle view={viewMode} onViewChange={handleViewChange} />
        </div>
      </div>

      {/* ── Loading skeleton ── */}
      {loading && documents.length === 0 && (
        viewMode === 'list' ? (
          <div className="space-y-1">
            {Array.from({ length: 6 }).map((_, i) => (
              <DocumentRowSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <DocumentGridCardSkeleton key={i} />
            ))}
          </div>
        )
      )}

      {/* ── Empty state (no documents at all) ── */}
      {!loading && allDocuments.length === 0 && (
        <EmptyState
          icon={FileText}
          title="Your library is empty"
          description="Intelligence documents from skills like meeting prep and company research will appear here."
        />
      )}

      {/* ── Empty state (search/tab yields nothing) ── */}
      {!loading && allDocuments.length > 0 && documents.length === 0 && (
        <EmptyState
          icon={Search}
          title="No documents found"
          description={
            debouncedSearch.trim()
              ? "Try a different search term or switch tabs."
              : "No documents in this category yet."
          }
          actionLabel={debouncedSearch.trim() ? "Clear search" : "Show all"}
          onAction={() => {
            handleClearSearch()
            setActiveTab('all')
          }}
        />
      )}

      {/* ── Document content ── */}
      {(!loading || documents.length > 0) && documents.length > 0 && (
        viewMode === 'list' ? (
          <div>
            {Array.from(grouped.entries()).map(([group, docs]) => (
              <div key={group} className="mb-6">
                <h2
                  className="flex items-center gap-2 uppercase tracking-wider mb-2 pl-4"
                  style={{
                    fontSize: '12px',
                    fontWeight: '600',
                    color: colors.secondaryText,
                    letterSpacing: '0.05em',
                  }}
                >
                  <span
                    className="w-0.5 h-3 rounded-full"
                    style={{ backgroundColor: 'rgba(233,77,53,0.3)' }}
                    aria-hidden="true"
                  />
                  {group}
                </h2>
                <div className="space-y-0.5">
                  {docs.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      document={doc}
                      onView={handleView}
                      onShare={handleShare}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div>
            {Array.from(grouped.entries()).map(([group, docs]) => (
              <div key={group} className="mb-8">
                <h2
                  className="flex items-center gap-2 uppercase tracking-wider mb-4"
                  style={{
                    fontSize: '12px',
                    fontWeight: '600',
                    color: colors.secondaryText,
                    letterSpacing: '0.05em',
                  }}
                >
                  <span
                    className="w-0.5 h-3 rounded-full"
                    style={{ backgroundColor: 'rgba(233,77,53,0.3)' }}
                    aria-hidden="true"
                  />
                  {group}
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {docs.map((doc, i) => (
                    <DocumentGridCard
                      key={doc.id}
                      document={doc}
                      index={i}
                      onView={handleView}
                      onShare={handleShare}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* ── Pagination ── */}
      {hasMore && !loading && (
        <div className="flex items-center justify-between mt-8 px-4">
          <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
            Showing {allDocuments.length} of {total} documents
          </span>
          <button
            type="button"
            onClick={handleLoadMore}
            className="px-5 py-2 rounded-xl text-sm font-medium border border-[var(--subtle-border)] transition-all duration-200 hover:border-[var(--brand-coral)] hover:text-[var(--brand-coral)] hover:shadow-sm"
            style={{
              backgroundColor: 'transparent',
              color: colors.secondaryText,
            }}
          >
            Load more
          </button>
        </div>
      )}

      {/* ── Loading more indicator ── */}
      {loading && allDocuments.length > 0 && (
        <div className="flex justify-center mt-4">
          <div className="w-6 h-6 border-2 border-[var(--subtle-border)] border-t-[var(--brand-coral)] rounded-full animate-spin" />
        </div>
      )}
    </div>
  )
}
