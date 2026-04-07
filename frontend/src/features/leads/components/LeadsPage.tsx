import { useEffect, useMemo, useState } from 'react'
import { Users, ChevronLeft, ChevronRight } from 'lucide-react'
import { AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { useLeads } from '../hooks/useLeads'
import { useLeadsPipeline } from '../hooks/useLeadsPipeline'
import { useLeadsColumns } from '../hooks/useLeadsColumns'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { LeadsFunnel } from './LeadsFunnel'
import { LeadsFilterBar } from './LeadsFilterBar'
import { LeadSidePanel } from './LeadSidePanel'
import type { LeadRow } from '../types/lead'
import { flattenLeadsToRows } from '../types/lead'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

const leadsTheme = themeQuartz.withParams({
  backgroundColor: '#FFFFFF',
  foregroundColor: '#121212',
  headerBackgroundColor: '#FAFAFA',
  headerTextColor: '#9CA3AF',
  borderColor: '#F3F4F6',
  accentColor: '#E94D35',
  rowHoverColor: 'rgba(233,77,53,0.04)',
  fontSize: 13,
  rowHeight: 48,
  headerHeight: 36,
  headerFontWeight: 600,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

export function LeadsPage() {
  // Filter state
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [fitTier, setFitTier] = useState<string | null>(null)
  const [purpose, setPurpose] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Pagination
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)

  // Side panel
  const [selectedRow, setSelectedRow] = useState<LeadRow | null>(null)

  // Debounce search (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  // Reset page on filter change
  useEffect(() => {
    setPage(0)
  }, [activeStage, fitTier, purpose, debouncedSearch, pageSize])

  // Data hooks
  const { data: leadsData, isLoading: isLeadsLoading } = useLeads({
    offset: page * pageSize,
    limit: pageSize,
    pipeline_stage: activeStage ?? undefined,
    fit_tier: fitTier ?? undefined,
    purpose: purpose ?? undefined,
    search: debouncedSearch || undefined,
  })

  const { data: pipeline, isLoading: isPipelineLoading } = useLeadsPipeline()

  const { columnDefs, initialState, onColumnStateChanged, gridApiRef } = useLeadsColumns()

  const leads = leadsData?.items ?? []
  const total = leadsData?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const funnel = pipeline?.funnel ?? {}
  const pipelineTotal = pipeline?.total ?? 0

  // Flatten leads into person-level rows, grouped by company
  const rows = useMemo(() => flattenLeadsToRows(leads), [leads])

  const isLoading = isLeadsLoading && rows.length === 0

  return (
    <div
      className="page-enter"
      style={{ padding: '32px 48px', background: 'var(--page-bg)' }}
    >
      <div className="mx-auto" style={{ maxWidth: '1440px' }}>
        {/* Title */}
        <div className="flex items-baseline gap-2" style={{ marginBottom: '24px' }}>
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: '-0.02em',
              color: 'var(--heading-text)',
              margin: 0,
            }}
          >
            Leads
          </h1>
          <span
            style={{
              fontSize: '28px',
              fontWeight: 400,
              color: 'var(--secondary-text)',
            }}
          >
            ({pipelineTotal})
          </span>
        </div>

        {/* Funnel */}
        <div style={{ marginBottom: '16px' }}>
          <LeadsFunnel
            funnel={funnel}
            total={pipelineTotal}
            activeStage={activeStage}
            onStageChange={setActiveStage}
            isLoading={isPipelineLoading}
          />
        </div>

        {/* Filter bar */}
        <div style={{ marginBottom: '16px' }}>
          <LeadsFilterBar
            search={search}
            onSearchChange={setSearch}
            activeStage={activeStage}
            onStageChange={setActiveStage}
            fitTier={fitTier}
            onFitTierChange={setFitTier}
            purpose={purpose}
            onPurposeChange={setPurpose}
          />
        </div>

        {/* Grid area */}
        {isLoading ? (
          <div style={{ background: 'var(--card-bg)', overflow: 'hidden', borderRadius: '8px' }}>
            {/* Funnel shimmer already shown above */}
            {/* Table skeleton */}
            <div
              className="flex items-center gap-3 px-3"
              style={{ height: '36px', background: '#FAFAFA', borderBottom: '1px solid #E5E7EB' }}
            >
              {[140, 110, 110, 60, 120, 80, 80, 70].map((w, i) => (
                <ShimmerSkeleton key={i} style={{ width: `${w}px`, height: '10px', borderRadius: '3px' }} />
              ))}
            </div>
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3"
                style={{ height: '44px', borderBottom: '1px solid #F3F4F6' }}
              >
                {[140, 100, 100, 50, 110, 70, 70, 60].map((w, j) => (
                  <ShimmerSkeleton key={j} style={{ width: `${w}px`, height: '12px', borderRadius: '3px' }} />
                ))}
              </div>
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ background: 'var(--card-bg)', borderRadius: '8px' }}>
            <EmptyState
              icon={Users}
              title="No leads in pipeline"
              description="Run a GTM pipeline to start discovering prospects"
            />
          </div>
        ) : (
          <>
            <div
              style={{
                height: 'calc(100vh - 320px)',
                width: '100%',
                overflow: 'hidden',
                borderRadius: '8px',
              }}
            >
              <AgGridReact<LeadRow>
                modules={[AllCommunityModule]}
                theme={leadsTheme}
                rowData={rows}
                columnDefs={columnDefs}
                initialState={initialState}
                onColumnResized={onColumnStateChanged}
                onColumnMoved={onColumnStateChanged}
                onColumnVisible={onColumnStateChanged}
                onGridReady={(e) => {
                  gridApiRef.current = e.api
                }}
                onRowClicked={(e) => {
                  if (e.data) setSelectedRow(e.data)
                }}
                defaultColDef={{ resizable: true, sortable: true }}
              />
            </div>

            {/* Pagination footer */}
            <div
              className="flex items-center justify-between flex-wrap gap-2"
              style={{
                marginTop: '8px',
                padding: '8px 0',
                borderTop: '1px solid var(--subtle-border)',
              }}
            >
              <span style={{ fontSize: '13px', color: 'var(--secondary-text)' }}>
                {total === 0
                  ? 'No results'
                  : `${page * pageSize + 1}\u2013${Math.min((page + 1) * pageSize, total)} of ${total}`}
              </span>

              <div className="flex items-center gap-3">
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  style={{
                    fontSize: '13px',
                    padding: '4px 8px',
                    borderRadius: '8px',
                    border: '1px solid var(--subtle-border)',
                    background: 'var(--card-bg)',
                    color: 'var(--heading-text)',
                    cursor: 'pointer',
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="flex items-center p-1 rounded hover:bg-[#F3F4F6] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ background: 'none', border: 'none', cursor: page === 0 ? 'not-allowed' : 'pointer' }}
                    aria-label="Previous page"
                  >
                    <ChevronLeft style={{ width: '16px', height: '16px', color: 'var(--secondary-text)' }} />
                  </button>
                  <span
                    style={{
                      fontSize: '13px',
                      color: 'var(--secondary-text)',
                      minWidth: '40px',
                      textAlign: 'center',
                    }}
                  >
                    {page + 1}/{totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="flex items-center p-1 rounded hover:bg-[#F3F4F6] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
                    }}
                    aria-label="Next page"
                  >
                    <ChevronRight style={{ width: '16px', height: '16px', color: 'var(--secondary-text)' }} />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Side Panel — shows clicked person's details */}
      {selectedRow && (
        <>
          <div
            className="fixed inset-0 z-30"
            style={{ background: 'rgba(0,0,0,0.2)' }}
            onClick={() => setSelectedRow(null)}
          />
          <LeadSidePanel
            row={selectedRow}
            onClose={() => setSelectedRow(null)}
          />
        </>
      )}

    </div>
  )
}
