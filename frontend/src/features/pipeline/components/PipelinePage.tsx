import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Inbox, ChevronLeft, ChevronRight } from 'lucide-react'
import { AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { usePipeline } from '../hooks/usePipeline'
import { usePipelineColumns } from '../hooks/usePipelineColumns'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { PipelineFilterBar } from './PipelineFilterBar'
import { PipelineViewTabs } from './PipelineViewTabs'
import type { PipelineView } from './PipelineViewTabs'
import { GraduationModal } from './GraduationModal'
import type { PipelineItem } from '../types/pipeline'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

const pipelineTheme = themeQuartz.withParams({
  backgroundColor: 'var(--card-bg)',
  foregroundColor: 'var(--body-text)',
  headerBackgroundColor: 'var(--card-bg)',
  headerTextColor: 'var(--secondary-text)',
  borderColor: 'var(--subtle-border)',
  accentColor: 'var(--brand-coral)',
  rowHoverColor: 'rgba(0,0,0,0.02)',
  fontSize: 14,
  rowHeight: 56,
  headerHeight: 40,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

export function PipelinePage() {
  const [searchParams] = useSearchParams()

  // Read active view from URL
  const viewParam = searchParams.get('view') as PipelineView | null
  const [activeView, setActiveView] = useState<PipelineView>(viewParam ?? 'all')

  // Filter state
  const [fitTier, setFitTier] = useState<string[]>([])
  const [outreachStatus, setOutreachStatus] = useState<string[]>([])
  const [search, setSearch] = useState('')

  // Pagination
  const [pageSize, setPageSize] = useState(50)
  const [page, setPage] = useState(0)

  // Graduation modal
  const [graduatingAccount, setGraduatingAccount] = useState<{ id: string; name: string } | null>(
    null
  )
  // Used for slide-out animation
  const [graduatingId, setGraduatingId] = useState<string | null>(null)

  // Derive server-side params based on active view
  // "stale" uses client-side filtering, so no server-side filter
  const serverFitTier =
    activeView === 'hot' ? ['Excellent', 'Strong'] : fitTier
  const serverOutreachStatus =
    activeView === 'replied' ? ['replied'] : outreachStatus

  const { data, isLoading } = usePipeline({
    offset: page * pageSize,
    limit: pageSize,
    fit_tier: serverFitTier.length > 0 ? serverFitTier : undefined,
    outreach_status: serverOutreachStatus.length > 0 ? serverOutreachStatus : undefined,
    search: search || undefined,
  })

  const allItems = data?.items ?? []
  const total = data?.total ?? 0

  // Client-side stale filter for the "stale" tab
  const items: PipelineItem[] =
    activeView === 'stale'
      ? allItems.filter((r) => (r.days_since_last_outreach ?? 0) > 14)
      : allItems

  // Replied rows float to top via postSortRows
  const postSortRows = useCallback(
    (params: { nodes: { data: PipelineItem }[] }) => {
      if (activeView === 'replied') {
        // Already filtered to replied — no re-sort needed
        return
      }
      // Push replied rows to top
      params.nodes.sort((a, b) => {
        const aReplied = a.data?.last_outreach_status === 'replied' ? -1 : 0
        const bReplied = b.data?.last_outreach_status === 'replied' ? -1 : 0
        return aReplied - bReplied
      })
    },
    [activeView]
  )

  const { columnDefs, initialState, onColumnStateChanged, gridApiRef } = usePipelineColumns()

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // Reset page when filters or view change
  useEffect(() => {
    setPage(0)
  }, [fitTier, outreachStatus, search, activeView, pageSize])

  // Handle graduation: add slide-out, then invalidation happens via useGraduate
  const handleGraduationSuccess = useCallback((id: string) => {
    setGraduatingId(id)
    setTimeout(() => {
      setGraduatingId(null)
    }, 300)
  }, [])

  return (
    <div
      className="page-enter"
      style={{ padding: spacing.pageDesktop, background: colors.pageBg }}
    >
      <div className="mx-auto" style={{ maxWidth: spacing.maxGrid }}>
        {/* Header */}
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
            Pipeline
          </h1>
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
            Prospect accounts ready for outreach
          </p>
        </div>

        {/* View Tabs */}
        <PipelineViewTabs
          activeView={activeView}
          onViewChange={(view) => {
            setActiveView(view)
            // Reset view-specific filters when switching tabs
            if (view !== 'hot') setFitTier([])
            if (view !== 'replied') setOutreachStatus([])
          }}
        />

        {/* Filter Bar */}
        <div style={{ marginBottom: spacing.element }}>
          <PipelineFilterBar
            fitTier={fitTier}
            onFitTierChange={(v) => {
              setFitTier(v)
              if (activeView === 'hot') setActiveView('all')
            }}
            outreachStatus={outreachStatus}
            onOutreachStatusChange={(v) => {
              setOutreachStatus(v)
              if (activeView === 'replied') setActiveView('all')
            }}
            search={search}
            onSearchChange={setSearch}
          />
        </div>

        {/* Grid area */}
        {isLoading ? (
          <div
            style={{
              background: colors.cardBg,
              borderRadius: '12px',
              border: `1px solid ${colors.subtleBorder}`,
              overflow: 'hidden',
            }}
          >
            {/* Header shimmer */}
            <div
              style={{
                height: '40px',
                borderBottom: `1px solid ${colors.subtleBorder}`,
                padding: '0 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
              }}
            >
              {[1.5, 1, 1, 0.6, 0.8, 0.8, 0.8, 0.6, 0.6].map((flex, i) => (
                <ShimmerSkeleton key={i} style={{ flex, height: '12px', borderRadius: '4px' }} />
              ))}
            </div>
            {/* Row shimmers */}
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                style={{
                  height: '56px',
                  borderBottom: `1px solid ${colors.subtleBorder}`,
                  padding: '0 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}
              >
                {[1.5, 1, 1, 0.6, 0.8, 0.8, 0.8, 0.6, 0.6].map((flex, j) => (
                  <ShimmerSkeleton key={j} style={{ flex, height: '14px', borderRadius: '4px' }} />
                ))}
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div
            style={{
              background: colors.cardBg,
              borderRadius: '12px',
              border: `1px solid ${colors.subtleBorder}`,
            }}
          >
            <EmptyState
              icon={Inbox}
              title="No prospects in pipeline"
              description="Add accounts to start building your pipeline"
            />
          </div>
        ) : (
          <>
            <div
              style={{
                height: 'calc(100vh - 360px)',
                width: '100%',
                borderRadius: '12px',
                overflow: 'hidden',
                border: `1px solid ${colors.subtleBorder}`,
              }}
            >
              <AgGridReact
                modules={[AllCommunityModule]}
                theme={pipelineTheme}
                rowData={items}
                columnDefs={columnDefs}
                initialState={initialState}
                onColumnResized={onColumnStateChanged}
                onColumnMoved={onColumnStateChanged}
                onColumnVisible={onColumnStateChanged}
                onGridReady={(e) => {
                  gridApiRef.current = e.api
                }}
                defaultColDef={{ resizable: true, sortable: true }}
                context={{
                  onGraduate: (id: string, name: string) =>
                    setGraduatingAccount({ id, name }),
                }}
                postSortRows={postSortRows}
                getRowStyle={(params) => {
                  const data = params.data as PipelineItem | undefined
                  if (!data) return undefined

                  if (graduatingId === data.id) {
                    return {
                      animation: 'slide-out-right 300ms ease-out forwards',
                      overflow: 'hidden',
                    }
                  }
                  if ((data.days_since_last_outreach ?? 0) > 14) {
                    return { background: 'var(--brand-tint-warmest)' }
                  }
                  if (data.last_outreach_status === 'replied') {
                    return { borderLeft: '3px solid var(--brand-coral)' }
                  }
                  return undefined
                }}
              />
            </div>

            {/* Pagination footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: '12px',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              {/* Left: showing info */}
              <span
                style={{ fontSize: typography.caption.size, color: colors.secondaryText }}
              >
                {total === 0
                  ? 'No results'
                  : `Showing ${page * pageSize + 1}–${Math.min((page + 1) * pageSize, total)} of ${total}`}
              </span>

              {/* Center: page size selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                  Rows per page:
                </span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  style={{
                    fontSize: typography.caption.size,
                    padding: '4px 8px',
                    borderRadius: '6px',
                    border: `1px solid ${colors.subtleBorder}`,
                    background: colors.cardBg,
                    color: colors.headingText,
                    cursor: 'pointer',
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>

              {/* Right: prev/next */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    border: `1px solid ${colors.subtleBorder}`,
                    background: colors.cardBg,
                    color: page === 0 ? colors.secondaryText : colors.headingText,
                    cursor: page === 0 ? 'not-allowed' : 'pointer',
                    opacity: page === 0 ? 0.5 : 1,
                  }}
                >
                  <ChevronLeft style={{ width: '14px', height: '14px' }} />
                </button>
                <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
                  {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    border: `1px solid ${colors.subtleBorder}`,
                    background: colors.cardBg,
                    color:
                      page >= totalPages - 1 ? colors.secondaryText : colors.headingText,
                    cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
                    opacity: page >= totalPages - 1 ? 0.5 : 1,
                  }}
                >
                  <ChevronRight style={{ width: '14px', height: '14px' }} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Graduation Modal */}
      {graduatingAccount && (
        <GraduationModal
          accountId={graduatingAccount.id}
          accountName={graduatingAccount.name}
          open={true}
          onClose={() => {
            handleGraduationSuccess(graduatingAccount.id)
            setGraduatingAccount(null)
          }}
        />
      )}
    </div>
  )
}
