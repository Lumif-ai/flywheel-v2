import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, X, FileText, ChevronDown, Check } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { Toast } from '@/components/ui/toast-notification'
import { EmptyState } from '@/components/ui/empty-state'
import { ViewToggle, type ViewMode } from '@/components/ui/view-toggle'
import { DocumentRow, DocumentRowSkeleton } from './DocumentRow'
import { DocumentGridCard, DocumentGridCardSkeleton } from './DocumentGridCard'
import {
  fetchDocuments,
  fetchDocumentTags,
  fetchDocumentCountsByType,
  shareDocument,
  deleteDocument,
  updateDocumentTags,
} from '../api'
import type { DocumentListItem, TypeCountItem, TagCountItem } from '../api'
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
  const twoWeeksAgo = new Date(today.getTime() - 14 * 86_400_000)
  const monthAgo = new Date(today.getTime() - 30 * 86_400_000)

  if (date >= today) return 'TODAY'
  if (date >= yesterday) return 'YESTERDAY'
  if (date >= weekAgo) return 'THIS WEEK'
  if (date >= twoWeeksAgo) return 'LAST WEEK'
  if (date >= monthAgo) return 'THIS MONTH'
  return 'EARLIER'
}

function groupByDate(docs: DocumentListItem[]): Map<string, DocumentListItem[]> {
  const groups = new Map<string, DocumentListItem[]>()
  const order = ['TODAY', 'YESTERDAY', 'THIS WEEK', 'LAST WEEK', 'THIS MONTH', 'EARLIER']
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
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50

// ---------------------------------------------------------------------------
// Tag Filter Bar component
// ---------------------------------------------------------------------------

function TagFilterBar({
  tags,
  activeTags,
  onToggle,
}: {
  tags: TagCountItem[]
  activeTags: string[]
  onToggle: (tag: string) => void
}) {
  if (tags.length === 0) return null
  return (
    <div
      className="flex items-center gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 mb-4"
      role="toolbar"
      aria-label="Filter by tag"
    >
      {tags.map((t) => {
        const isActive = activeTags.includes(t.tag)
        return (
          <button
            key={t.tag}
            type="button"
            role="button"
            aria-pressed={isActive}
            onClick={() => onToggle(t.tag)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-150 border"
            style={{
              backgroundColor: isActive ? 'rgba(233,77,53,0.1)' : 'rgba(0,0,0,0.03)',
              borderColor: isActive ? 'rgba(233,77,53,0.3)' : 'transparent',
              color: isActive ? 'var(--brand-coral)' : colors.secondaryText,
            }}
          >
            {t.tag}
            <span className="opacity-60">{t.count}</span>
          </button>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Company Filter Dropdown component
// ---------------------------------------------------------------------------

function CompanyFilter({
  documents,
  selected,
  onSelect,
}: {
  documents: DocumentListItem[]
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  // Derive companies from documents
  const companies = useMemo(() => {
    const map = new Map<string, { id: string; name: string; count: number }>()
    for (const doc of documents) {
      if (doc.account_id && doc.account_name) {
        const existing = map.get(doc.account_id)
        if (existing) {
          existing.count++
        } else {
          map.set(doc.account_id, { id: doc.account_id, name: doc.account_name, count: 1 })
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count)
  }, [documents])

  const filtered = search
    ? companies.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))
    : companies

  const selectedName = selected
    ? companies.find((c) => c.id === selected)?.name ?? 'Company'
    : null

  if (companies.length === 0) return null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--subtle-border)] text-sm transition-all duration-150 hover:border-[var(--brand-coral)]"
        style={{ color: selected ? colors.headingText : colors.secondaryText }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selectedName || 'Company'}
        <ChevronDown size={14} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => { setOpen(false); setSearch('') }} />
          <div className="absolute left-0 top-full mt-1 z-20 bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-lg shadow-lg py-1 min-w-[220px] max-h-[300px] overflow-auto">
            {/* Search */}
            <div className="px-2 pb-1">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search companies..."
                className="w-full h-8 px-2 rounded-md border border-[var(--subtle-border)] text-sm outline-none focus:border-[var(--brand-coral)]"
                autoFocus
              />
            </div>
            {/* All companies option */}
            <button
              type="button"
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[rgba(233,77,53,0.04)] transition-colors"
              style={{ color: !selected ? 'var(--brand-coral)' : colors.headingText }}
              onClick={() => { onSelect(null); setOpen(false); setSearch('') }}
            >
              {!selected && <Check size={14} />}
              <span className={!selected ? '' : 'ml-5'}>All Companies</span>
            </button>
            {filtered.map((c) => (
              <button
                key={c.id}
                type="button"
                className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[rgba(233,77,53,0.04)] transition-colors"
                style={{ color: selected === c.id ? 'var(--brand-coral)' : colors.headingText }}
                onClick={() => { onSelect(c.id); setOpen(false); setSearch('') }}
              >
                {selected === c.id && <Check size={14} />}
                <span className={selected === c.id ? '' : 'ml-5'}>{c.name}</span>
                <span className="ml-auto text-xs opacity-50">{c.count}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add Tag Modal (simple inline input)
// ---------------------------------------------------------------------------

function AddTagInput({
  docId,
  existingTags,
  onDone,
}: {
  docId: string
  existingTags: string[]
  onDone: () => void
}) {
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = async () => {
    const tag = value.trim().toLowerCase()
    if (!tag || existingTags.includes(tag)) return
    setSaving(true)
    try {
      await updateDocumentTags(docId, { add: [tag] })
      onDone()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onDone}>
      <div
        className="bg-[var(--card-bg)] rounded-xl p-4 shadow-xl border border-[var(--subtle-border)] w-[320px]"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-medium mb-2" style={{ color: colors.headingText }}>Add Tag</h3>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
          placeholder="e.g. series-a, board-prep"
          className="w-full h-9 px-3 rounded-lg border border-[var(--subtle-border)] text-sm outline-none focus:border-[var(--brand-coral)]"
          maxLength={50}
        />
        <p className="text-xs mt-1 opacity-50" style={{ color: colors.secondaryText }}>
          Lowercase, alphanumeric and hyphens only
        </p>
        <div className="flex justify-end gap-2 mt-3">
          <button
            type="button"
            onClick={onDone}
            className="px-3 py-1.5 rounded-lg text-sm"
            style={{ color: colors.secondaryText }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !value.trim()}
            className="px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: 'var(--brand-coral)' }}
          >
            {saving ? 'Adding...' : 'Add'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function DocumentLibrary() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const [activeTab, setActiveTab] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode)
  const [activeTags, setActiveTags] = useState<string[]>([])
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null)
  const [shareToast, setShareToast] = useState<string | null>(null)
  const [addTagDoc, setAddTagDoc] = useState<DocumentListItem | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

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

  // Build filter params
  const filterParams = useMemo(() => ({
    document_type: activeTab === 'all' ? undefined : activeTab,
    account_id: selectedCompany ?? undefined,
    tags: activeTags.length > 0 ? activeTags : undefined,
    search: debouncedSearch || undefined,
  }), [activeTab, selectedCompany, activeTags, debouncedSearch])

  // Infinite query for documents
  const {
    data,
    isLoading: loading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['documents', filterParams],
    queryFn: ({ pageParam }) =>
      fetchDocuments({
        ...filterParams,
        cursor: pageParam ?? undefined,
        limit: PAGE_SIZE,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    enabled: !!user,
  })

  const allDocuments = useMemo(
    () => data?.pages.flatMap((p) => p.documents) ?? [],
    [data],
  )
  const total = data?.pages[0]?.total ?? 0

  // Fetch type counts (server-side)
  const { data: typeCounts } = useQuery({
    queryKey: ['document-counts', { account_id: selectedCompany, tags: activeTags, search: debouncedSearch }],
    queryFn: () => fetchDocumentCountsByType({
      account_id: selectedCompany ?? undefined,
      tags: activeTags.length > 0 ? activeTags : undefined,
      search: debouncedSearch || undefined,
    }),
    enabled: !!user,
  })

  // Fetch tags (server-side, scoped to current filters minus tags)
  const { data: tagOptions } = useQuery({
    queryKey: ['document-tags', { document_type: filterParams.document_type, account_id: selectedCompany, search: debouncedSearch }],
    queryFn: () => fetchDocumentTags({
      document_type: filterParams.document_type,
      account_id: selectedCompany ?? undefined,
      search: debouncedSearch || undefined,
    }),
    enabled: !!user,
  })

  // Build tabs from type counts
  const tabs = useMemo(() => {
    const allCount = typeCounts?.reduce((sum, t) => sum + t.count, 0) ?? total
    const entries = (typeCounts ?? []).sort((a, b) => b.count - a.count)
    return [
      { key: 'all', label: 'All', count: allCount },
      ...entries.map((t) => ({
        key: t.document_type,
        label: getTypeStyle(t.document_type).label,
        count: t.count,
      })),
    ]
  }, [typeCounts, total])

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const handleToggleTag = useCallback((tag: string) => {
    setActiveTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    )
  }, [])

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

  const handleDelete = async (doc: DocumentListItem) => {
    const confirmed = window.confirm(`Delete "${doc.title}"? This action cannot be undone.`)
    if (!confirmed) return
    try {
      await deleteDocument(doc.id)
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
      await queryClient.invalidateQueries({ queryKey: ['document-counts'] })
      await queryClient.invalidateQueries({ queryKey: ['document-tags'] })
    } catch (err) {
      console.error('Failed to delete document:', err)
    }
  }

  const handleView = (doc: DocumentListItem) => {
    navigate(`/documents/${doc.id}`)
  }

  const handleClearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
  }

  const handleClearFilters = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    setActiveTab('all')
    setActiveTags([])
    setSelectedCompany(null)
  }

  const grouped = groupByDate(allDocuments)

  return (
    <div
      className="mx-auto w-full page-enter"
      style={{
        maxWidth: spacing.maxGrid,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      <Toast message="Link copied to clipboard" visible={!!shareToast} onDismiss={() => setShareToast(null)} />

      {/* Add Tag Modal */}
      {addTagDoc && (
        <AddTagInput
          docId={addTagDoc.id}
          existingTags={addTagDoc.tags}
          onDone={() => setAddTagDoc(null)}
        />
      )}

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

      {/* ── Type Tabs ── */}
      <div
        className="flex items-center gap-1 overflow-x-auto mb-4 -mx-1 px-1"
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

      {/* ── Filters row: Company dropdown + Search + View toggle ── */}
      <div className="flex items-center gap-3 mb-2">
        <CompanyFilter
          documents={allDocuments}
          selected={selectedCompany}
          onSelect={setSelectedCompany}
        />
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

      {/* ── Tag filter bar ── */}
      <TagFilterBar
        tags={tagOptions ?? []}
        activeTags={activeTags}
        onToggle={handleToggleTag}
      />

      {/* ── Loading skeleton ── */}
      {loading && allDocuments.length === 0 && (
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
      {!loading && total === 0 && !debouncedSearch && activeTags.length === 0 && !selectedCompany && activeTab === 'all' && (
        <EmptyState
          icon={FileText}
          title="Your library is empty"
          description="Documents from meeting prep, account research, and skills will appear here automatically."
        />
      )}

      {/* ── Empty state (filter yields nothing) ── */}
      {!loading && allDocuments.length === 0 && (debouncedSearch || activeTags.length > 0 || selectedCompany || activeTab !== 'all') && (
        <EmptyState
          icon={Search}
          title="No documents match your filters"
          description="Try removing a filter or search term."
          actionLabel="Clear filters"
          onAction={handleClearFilters}
        />
      )}

      {/* ── Document content ── */}
      {allDocuments.length > 0 && (
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
                      onAddTag={setAddTagDoc}
                      onDelete={handleDelete}
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
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* ── Infinite scroll sentinel ── */}
      <div ref={sentinelRef} className="h-4" />

      {/* ── Loading more indicator ── */}
      {isFetchingNextPage && (
        <div className="flex justify-center mt-4 mb-8">
          <div className="w-6 h-6 border-2 border-[var(--subtle-border)] border-t-[var(--brand-coral)] rounded-full animate-spin" />
        </div>
      )}

      {/* ── Footer count ── */}
      {allDocuments.length > 0 && !hasNextPage && (
        <div className="text-center mt-4 mb-8">
          <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
            {allDocuments.length} of {total} documents
          </span>
        </div>
      )}
    </div>
  )
}
