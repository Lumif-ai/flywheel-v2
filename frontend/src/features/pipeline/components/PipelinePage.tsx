import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams, useNavigate, useLocation } from 'react-router'
import { Inbox, ChevronLeft, ChevronRight } from 'lucide-react'
import { AllCommunityModule, themeQuartz } from 'ag-grid-community'
import type { CellKeyDownEvent, GridApi } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { usePipeline } from '../hooks/usePipeline'
import { usePipelineColumns } from '../hooks/usePipelineColumns'
import { useContacts } from '../hooks/useContacts'
import { useContactColumns } from '../hooks/useContactColumns'
import { usePipelineMutation } from '../hooks/usePipelineMutation'
import { usePipelineCreate } from '../hooks/usePipelineCreate'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { PipelineViewTabs } from './PipelineViewTabs'
import { PipelineToolbar } from './PipelineToolbar'
import { PipelineFilterBar } from './PipelineFilterBar'
import { ContactFilterBar } from './ContactFilterBar'
import { QuickAddRow } from './QuickAddRow'
import { PipelineSidePanel } from './PipelineSidePanel'
import { ContactDetailPanel } from './ContactDetailPanel'
import { ContactDetailRow } from './ContactDetailRow'
import { ExpandToggleCell } from './cell-renderers/ExpandToggleCell'
import type {
  PipelineListItem,
  PipelineGridRow,
  PipelineDetailRow,
  ContactListItem,
  ViewTab,
  GridMode,
} from '../types/pipeline'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

const pipelineTheme = themeQuartz.withParams({
  backgroundColor: '#FFFFFF',
  foregroundColor: '#121212',
  headerBackgroundColor: '#FAFAFA',
  headerTextColor: '#9CA3AF',
  borderColor: '#F3F4F6',
  accentColor: '#E94D35',
  rowHoverColor: '#FAFAFA',
  fontSize: 13,
  rowHeight: 44,
  headerHeight: 36,
  headerFontWeight: 600,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

export function PipelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Refs for scroll/selection restoration on back-navigation
  const pendingRestoreRef = useRef<string | null>(null)
  const gridReadyRef = useRef(false)
  // Guard: skip state→URL write when URL→state sync just ran (prevents circular overwrite)
  const skipUrlWriteRef = useRef(false)

  // Mode: contacts (default) or companies — force companies when relationshipType filter is active
  const modeParam = searchParams.get('mode') as GridMode | null
  const relTypeFromUrl = searchParams.get('relationshipType')
  const [mode, setMode] = useState<GridMode>(relTypeFromUrl ? 'companies' : (modeParam ?? 'contacts'))
  const isContactMode = mode === 'contacts'

  // Read active view and all filter params from URL on mount
  const viewParam = searchParams.get('view') as ViewTab | null
  const searchParam = searchParams.get('q') ?? ''
  const stageParam = searchParams.get('stage')
  const fitTierParam = searchParams.get('fitTier')
  const relTypeParam = searchParams.get('relationshipType')
  const sourceParam = searchParams.get('source')
  const [activeView, setActiveView] = useState<ViewTab>(viewParam ?? 'all')

  // Company-mode filter state — initialized from URL params
  const [fitTier, setFitTier] = useState<string[]>(fitTierParam ? fitTierParam.split(',') : [])
  const [stage, setStage] = useState<string[]>(stageParam ? stageParam.split(',') : [])
  const [relationshipType, setRelationshipType] = useState<string[]>(relTypeParam ? relTypeParam.split(',') : [])
  const [source, setSource] = useState(sourceParam ?? '')
  const [search, setSearch] = useState(searchParam)
  const [showFilters, setShowFilters] = useState(
    !!(stageParam || fitTierParam || relTypeParam || sourceParam)
  )

  // Sync mode with URL: relationshipType → companies, no params → contacts
  useEffect(() => {
    const relType = searchParams.get('relationshipType')
    const modeFromUrl = searchParams.get('mode') as GridMode | null
    if (relType) {
      skipUrlWriteRef.current = true
      setMode('companies')
      setRelationshipType(relType.split(','))
      setShowFilters(true)
    } else if (!modeFromUrl) {
      // No relationshipType and no explicit mode — reset to contacts default
      skipUrlWriteRef.current = true
      setMode('contacts')
      setRelationshipType([])
    }
  }, [searchParams])

  // Contact-mode filter state
  const [contactCompany, setContactCompany] = useState('')
  const [contactStatus, setContactStatus] = useState('')
  const [contactChannel, setContactChannel] = useState('')
  const [contactVariant, setContactVariant] = useState('')
  const [contactStepNumber, setContactStepNumber] = useState('')

  // Pagination
  const [pageSize, setPageSize] = useState(50)
  const [page, setPage] = useState(0)

  // Company-mode sort
  const [sortModel, setSortModel] = useState<{ colId: string; sort: 'asc' | 'desc' } | null>(null)

  // Contact-mode sort
  const [contactSortModel, setContactSortModel] = useState<{ colId: string; sort: 'asc' | 'desc' } | null>(null)

  // Show retired toggle
  const [showRetired, setShowRetired] = useState(false)

  // Side panel (company mode only)
  const [selectedItem, setSelectedItem] = useState<PipelineListItem | null>(null)

  // Contact detail panel (contact mode only)
  const [selectedContact, setSelectedContact] = useState<ContactListItem | null>(null)

  // Expand/collapse state for detail rows (company mode)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const handleToggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  // Map contact sort colId to API sort_by param
  const contactSortBy = useMemo(() => {
    if (!contactSortModel) return undefined
    const sortMap: Record<string, string> = {
      name: 'name',
      company_name: 'company_name',
      email: 'email',
      contact_status: 'status',
      next_step: 'next_step_priority',
      occurred_at: 'occurred_at',
    }
    return sortMap[contactSortModel.colId] ?? contactSortModel.colId
  }, [contactSortModel])

  // URL sync: update URL when any filter changes
  useEffect(() => {
    // Skip if this render was triggered by URL→state sync (prevents circular overwrite)
    if (skipUrlWriteRef.current) {
      skipUrlWriteRef.current = false
      return
    }
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)

      // Mode
      if (mode === 'contacts') next.delete('mode')
      else next.set('mode', mode)

      if (isContactMode) {
        // Contact filters
        if (contactCompany) next.set('company', contactCompany); else next.delete('company')
        if (contactStatus) next.set('status', contactStatus); else next.delete('status')
        if (contactChannel) next.set('channel', contactChannel); else next.delete('channel')
        if (contactVariant) next.set('variant', contactVariant); else next.delete('variant')
        if (contactStepNumber) next.set('step', contactStepNumber); else next.delete('step')
        // Remove company-mode URL params
        next.delete('stage'); next.delete('fitTier'); next.delete('relationshipType'); next.delete('source')
        next.delete('view'); next.delete('q')
      } else {
        // Company filters
        if (activeView === 'all') next.delete('view'); else next.set('view', activeView)
        if (search) next.set('q', search); else next.delete('q')
        if (stage.length) next.set('stage', stage.join(',')); else next.delete('stage')
        if (fitTier.length) next.set('fitTier', fitTier.join(',')); else next.delete('fitTier')
        if (relationshipType.length) next.set('relationshipType', relationshipType.join(',')); else next.delete('relationshipType')
        if (source) next.set('source', source); else next.delete('source')
        // Remove contact-mode URL params
        next.delete('company'); next.delete('status'); next.delete('channel'); next.delete('variant'); next.delete('step')
      }

      return next
    }, { replace: true })
  }, [mode, isContactMode, activeView, search, stage, fitTier, relationshipType, source, contactCompany, contactStatus, contactChannel, contactVariant, contactStepNumber, setSearchParams])

  // Map view tab to API param
  const apiView: ViewTab | undefined = activeView === 'all' ? undefined : activeView

  // Company data query
  const { data, isLoading } = usePipeline({
    offset: page * pageSize,
    limit: pageSize,
    search: search || undefined,
    sort_by: sortModel?.colId,
    sort_dir: sortModel?.sort,
    stage: stage.length > 0 ? stage : undefined,
    fit_tier: fitTier.length > 0 ? fitTier : undefined,
    relationship_type: relationshipType.length > 0 ? relationshipType : undefined,
    source: source || undefined,
    view: apiView,
    include_retired: showRetired || undefined,
  })

  // Contact data query
  const contactQuery = useContacts({
    offset: page * pageSize,
    limit: pageSize,
    sort_by: contactSortBy,
    sort_dir: contactSortModel?.sort,
    company: contactCompany || undefined,
    status: contactStatus || undefined,
    channel: contactChannel || undefined,
    variant: contactVariant || undefined,
    step_number: contactStepNumber ? Number(contactStepNumber) : undefined,
    include_retired: showRetired || undefined,
    enabled: isContactMode,
  })

  const mutation = usePipelineMutation()
  const createMutation = usePipelineCreate()

  // Current data based on mode
  const currentItems = isContactMode ? (contactQuery.data?.items ?? []) : (data?.items ?? [])
  const currentTotal = isContactMode ? (contactQuery.data?.total ?? 0) : (data?.total ?? 0)
  const currentLoading = isContactMode ? contactQuery.isLoading : isLoading

  const items = data?.items ?? []

  const { columnDefs, restoreColumnState, onColumnStateChanged, gridApiRef } = usePipelineColumns()
  const {
    columnDefs: contactColumnDefs,
    restoreColumnState: restoreContactColumnState,
    onColumnStateChanged: onContactColumnStateChanged,
    gridApiRef: contactGridApiRef,
  } = useContactColumns()

  // Build grid rows with detail rows interleaved after expanded items (company mode)
  const gridRows = useMemo<PipelineGridRow[]>(() => {
    const rows: PipelineGridRow[] = []
    for (const item of items) {
      rows.push({ ...item, _isDetailRow: false as const })
      if (expandedIds.has(item.id)) {
        rows.push({
          _isDetailRow: true as const,
          _parentId: item.id,
          _parentName: item.name,
          id: `detail-${item.id}`,
        })
      }
    }
    return rows
  }, [items, expandedIds])

  // Override expand column's cellRendererParams with current state (company mode)
  const columnsWithExpand = useMemo(() => {
    return columnDefs.map((col) => {
      if ((col as any).colId === 'expand') {
        return {
          ...col,
          cellRendererParams: { expandedIds, onToggle: handleToggleExpand },
        }
      }
      return col
    })
  }, [columnDefs, expandedIds, handleToggleExpand])

  const totalPages = Math.max(1, Math.ceil(currentTotal / pageSize))

  // Reset page when filters or view change
  useEffect(() => {
    setPage(0)
  }, [fitTier, stage, relationshipType, source, search, activeView, pageSize, contactCompany, contactStatus, contactChannel, contactVariant, contactStepNumber])

  // Mode change handler
  const handleModeChange = useCallback((newMode: GridMode) => {
    setMode(newMode)
    setPage(0)
    setSelectedContact(null)
    gridReadyRef.current = false
  }, [])

  // Handle view change: reset manual filters to avoid conflicting states
  const handleViewChange = useCallback((view: ViewTab) => {
    setActiveView(view)
    setStage([])
    setFitTier([])
    setRelationshipType([])
    setSource('')
  }, [])

  // Clear all company-mode filters
  const handleClearFilters = useCallback(() => {
    setStage([])
    setFitTier([])
    setRelationshipType([])
    setSource('')
  }, [])

  // Clear all contact-mode filters
  const handleClearContactFilters = useCallback(() => {
    setContactCompany('')
    setContactStatus('')
    setContactChannel('')
    setContactVariant('')
    setContactStepNumber('')
  }, [])

  // Quick-add handler (company mode only)
  const handleQuickAdd = useCallback((name: string) => {
    createMutation.mutate({ name, entity_type: 'company' })
  }, [createMutation])

  // Inline editing handler (company mode)
  const onCellValueChanged = useCallback(
    (event: { data: PipelineListItem; colDef: { field?: string }; newValue: unknown; oldValue: unknown }) => {
      if (event.newValue === event.oldValue) return
      const field = event.colDef.field
      if (!field) return
      mutation.mutate({
        id: event.data.id,
        data: { [field]: event.newValue },
      })
    },
    [mutation]
  )

  // Sort sync (company mode)
  const onSortChanged = useCallback(() => {
    const api = gridApiRef.current
    if (!api) return
    const colState = api.getColumnState()
    const sorted = colState.find((c) => c.sort)
    if (sorted && sorted.colId && sorted.sort) {
      setSortModel({ colId: sorted.colId, sort: sorted.sort })
    } else {
      setSortModel(null)
    }
  }, [gridApiRef])

  // Sort sync (contact mode)
  const onContactSortChanged = useCallback(() => {
    const api = contactGridApiRef.current
    if (!api) return
    const colState = api.getColumnState()
    const sorted = colState.find((c) => c.sort)
    if (sorted?.colId && sorted?.sort) {
      setContactSortModel({ colId: sorted.colId, sort: sorted.sort })
    } else {
      setContactSortModel(null)
    }
  }, [contactGridApiRef])

  // Keyboard navigation for side panel (company mode only)
  const onCellKeyDown = useCallback(
    (e: CellKeyDownEvent<PipelineGridRow>) => {
      const keyEvent = e.event as KeyboardEvent | undefined
      if (!keyEvent) return
      if (e.data?._isDetailRow) return
      if (keyEvent.key === 'Enter' && e.data && !e.colDef.editable) {
        setSelectedItem(e.data as PipelineListItem)
      } else if (keyEvent.key === 'Escape') {
        setSelectedItem(null)
      }
    },
    []
  )

  // Open full profile handler
  const handleOpenProfile = useCallback(
    (id: string) => {
      navigate(`/pipeline/${id}`, { state: { from: '/pipeline', selectedId: id, page } })
    },
    [navigate, page]
  )

  // --- Scroll / selection restoration on back-navigation ---

  // Shared restore logic -- called from either data-load or grid-ready
  const attemptRestore = useCallback(() => {
    if (!pendingRestoreRef.current || items.length === 0) return
    if (!gridReadyRef.current) return // grid not mounted yet, wait

    const item = items.find((i) => i.id === pendingRestoreRef.current)
    if (item) {
      setSelectedItem(item)
      const api = gridApiRef.current
      if (api) {
        const rowNode = api.getRowNode(item.id)
        if (rowNode) {
          api.ensureNodeVisible(rowNode, 'middle')
        }
      }
    }
    pendingRestoreRef.current = null
  }, [items, gridApiRef])

  // Read restore state from location on mount
  useEffect(() => {
    const state = location.state as {
      restoreSelectedId?: string
      restorePage?: number
    } | null

    if (state?.restorePage !== undefined) {
      setPage(state.restorePage)
    }
    if (state?.restoreSelectedId) {
      pendingRestoreRef.current = state.restoreSelectedId
    }
    // Clear location state to prevent re-triggering on subsequent renders
    if (state?.restoreSelectedId || state?.restorePage !== undefined) {
      window.history.replaceState({}, '')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- run once on mount only

  // Trigger restore when items load
  useEffect(() => {
    attemptRestore()
  }, [attemptRestore])

  // Grid ready handler
  const handleGridReady = useCallback(
    (e: { api: GridApi }) => {
      if (isContactMode) {
        contactGridApiRef.current = e.api
      } else {
        gridApiRef.current = e.api
      }
      gridReadyRef.current = true
      if (isContactMode) {
        restoreContactColumnState(e.api)
      } else {
        restoreColumnState(e.api)
        attemptRestore()
      }
    },
    [isContactMode, attemptRestore, restoreColumnState, restoreContactColumnState, gridApiRef, contactGridApiRef]
  )

  // Determine grid props based on mode
  const currentRowData = isContactMode ? (currentItems as ContactListItem[]) : gridRows
  const currentColumnDefs = isContactMode ? contactColumnDefs : columnsWithExpand

  return (
    <div
      className="page-enter"
      style={{ padding: '20px 24px', background: '#FFFFFF' }}
    >
      <style>{`
        .row-stale {
          background: rgba(245, 158, 11, 0.06) !important;
          border-left: 3px solid #F59E0B !important;
        }
        .row-retired {
          opacity: 0.5;
        }
        .row-detail-full-width {
          background: #FAFAFA !important;
        }
      `}</style>
      <div className="mx-auto" style={{ maxWidth: '1440px' }}>
        {/* Header -- title + mode toggle + view tabs inline */}
        <div className="flex items-center gap-4 mb-1">
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              lineHeight: 1.3,
              letterSpacing: '-0.01em',
              color: '#121212',
            }}
          >
            Pipeline
          </h1>

          {/* Mode toggle: Contacts | Companies */}
          <div className="flex items-center gap-0.5" style={{
            background: '#F3F4F6', borderRadius: '8px', padding: '2px',
          }}>
            <button
              onClick={() => handleModeChange('contacts')}
              style={{
                padding: '4px 12px', fontSize: '12px', fontWeight: 500,
                borderRadius: '6px', border: 'none', cursor: 'pointer',
                background: isContactMode ? '#FFFFFF' : 'transparent',
                color: isContactMode ? '#121212' : '#9CA3AF',
                boxShadow: isContactMode ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 150ms',
              }}
            >Contacts</button>
            <button
              onClick={() => handleModeChange('companies')}
              style={{
                padding: '4px 12px', fontSize: '12px', fontWeight: 500,
                borderRadius: '6px', border: 'none', cursor: 'pointer',
                background: !isContactMode ? '#FFFFFF' : 'transparent',
                color: !isContactMode ? '#121212' : '#9CA3AF',
                boxShadow: !isContactMode ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 150ms',
              }}
            >Companies</button>
          </div>

          {/* View tabs only in companies mode */}
          {!isContactMode && (
            <PipelineViewTabs
              activeView={activeView}
              onViewChange={handleViewChange}
            />
          )}
        </div>

        {/* Toolbar */}
        <PipelineToolbar
          search={search}
          onSearchChange={setSearch}
          onToggleFilters={() => setShowFilters((v) => !v)}
          filtersVisible={showFilters}
          showRetired={showRetired}
          onShowRetiredChange={setShowRetired}
          filters={{
            stage: stage.length > 0 ? stage : undefined,
            fitTier: fitTier.length > 0 ? fitTier : undefined,
            relationshipType: relationshipType.length > 0 ? relationshipType : undefined,
            source: source || undefined,
            view: activeView !== 'all' ? activeView : undefined,
            search: search || undefined,
          }}
          sort={sortModel}
        />

        {/* Filter bar (conditional per mode) */}
        {showFilters && (
          isContactMode ? (
            <ContactFilterBar
              company={contactCompany}
              onCompanyChange={setContactCompany}
              status={contactStatus}
              onStatusChange={setContactStatus}
              channel={contactChannel}
              onChannelChange={setContactChannel}
              variant={contactVariant}
              onVariantChange={setContactVariant}
              stepNumber={contactStepNumber}
              onStepNumberChange={setContactStepNumber}
              onClear={handleClearContactFilters}
            />
          ) : (
            <PipelineFilterBar
              stage={stage}
              onStageChange={setStage}
              fitTier={fitTier}
              onFitTierChange={setFitTier}
              relationshipType={relationshipType}
              onRelationshipTypeChange={setRelationshipType}
              source={source}
              onSourceChange={setSource}
              onClear={handleClearFilters}
            />
          )
        )}

        {/* Grid area */}
        {currentLoading ? (
          <div style={{ background: '#FFFFFF', overflow: 'hidden' }}>
            <div
              className="flex items-center gap-3 px-3"
              style={{ height: '36px', background: '#FAFAFA', borderBottom: '1px solid #E5E7EB' }}
            >
              {[120, 100, 100, 60, 80, 80, 80, 60, 70].map((w, i) => (
                <ShimmerSkeleton key={i} style={{ width: `${w}px`, height: '10px', borderRadius: '3px' }} />
              ))}
            </div>
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3"
                style={{ height: '44px', borderBottom: '1px solid #F3F4F6' }}
              >
                {[140, 110, 100, 60, 70, 80, 70, 50, 70].map((w, j) => (
                  <ShimmerSkeleton key={j} style={{ width: `${w}px`, height: '12px', borderRadius: '3px' }} />
                ))}
              </div>
            ))}
          </div>
        ) : currentItems.length === 0 ? (
          <div style={{ background: '#FFFFFF' }}>
            <EmptyState
              icon={Inbox}
              title={isContactMode ? 'No contacts found' : 'No entries in pipeline'}
              description={isContactMode ? 'Contacts will appear here once companies have contacts added' : 'Add entries to start building your pipeline'}
            />
          </div>
        ) : (
          <>
            <div
              style={{
                height: 'calc(100dvh - 160px)',
                width: (!isContactMode && selectedItem) ? 'calc(100% - 420px)' : (isContactMode && selectedContact) ? 'calc(100% - 480px)' : '100%',
                overflow: 'hidden',
                transition: 'width 200ms ease-out',
              }}
            >
              <AgGridReact
                key={mode}
                modules={[AllCommunityModule]}
                theme={pipelineTheme}
                rowData={currentRowData}
                columnDefs={currentColumnDefs}
                onColumnResized={isContactMode ? onContactColumnStateChanged : onColumnStateChanged}
                onColumnMoved={isContactMode ? onContactColumnStateChanged : onColumnStateChanged}
                onColumnVisible={isContactMode ? onContactColumnStateChanged : onColumnStateChanged}
                getRowId={(params) => {
                  if (params.data._isDetailRow) return params.data.id
                  return isContactMode ? `c-${params.data.id}` : params.data.id
                }}
                onGridReady={handleGridReady}
                onRowClicked={(e) => {
                  if (e.data?._isDetailRow) return
                  if (isContactMode && e.data) {
                    setSelectedContact(e.data as ContactListItem)
                  } else if (e.data) {
                    setSelectedItem(e.data as PipelineListItem)
                  }
                }}
                onCellValueChanged={isContactMode ? undefined : onCellValueChanged}
                onSortChanged={isContactMode ? onContactSortChanged : onSortChanged}
                onCellKeyDown={isContactMode ? (e) => {
                  const keyEvent = e.event as KeyboardEvent | undefined
                  if (keyEvent?.key === 'Escape') setSelectedContact(null)
                } : onCellKeyDown}
                isFullWidthRow={isContactMode ? undefined : (params) => params.rowNode.data?._isDetailRow === true}
                fullWidthCellRenderer={isContactMode ? undefined : (params: { data: PipelineDetailRow }) => {
                  const d = params.data
                  return <ContactDetailRow entryId={d._parentId} entryName={d._parentName} />
                }}
                getRowHeight={isContactMode ? undefined : (params) => {
                  if (params.data?._isDetailRow) {
                    const parentId = (params.data as any)._parentId
                    const parent = items.find((i) => i.id === parentId)
                    const contactCount = parent?.contact_count ?? 5
                    return Math.min(32 + contactCount * 28 + 16, 400)
                  }
                  return 44
                }}
                getRowClass={isContactMode ? undefined : (params) => {
                  if (params.data?._isDetailRow) return 'row-detail-full-width'
                  const d = params.data as PipelineListItem | undefined
                  if (d?.retired_at) return 'row-retired'
                  if (d?.stale_notified_at) return 'row-stale'
                  return undefined
                }}
                defaultColDef={{ resizable: true, sortable: true }}
                sortingOrder={['asc', 'desc', null]}
              />
            </div>

            {/* Quick-add row (company mode only) */}
            {!isContactMode && <QuickAddRow onAdd={handleQuickAdd} />}

            {/* Pagination footer */}
            <div
              className="flex items-center justify-between flex-wrap gap-2"
              style={{ marginTop: '8px', padding: '4px 0' }}
            >
              <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
                {currentTotal === 0
                  ? 'No results'
                  : `${page * pageSize + 1}\u2013${Math.min((page + 1) * pageSize, currentTotal)} of ${currentTotal}`}
              </span>

              <div className="flex items-center gap-2">
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  style={{
                    fontSize: '12px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    border: '1px solid #E5E7EB',
                    background: '#FFFFFF',
                    color: '#121212',
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
                  >
                    <ChevronLeft style={{ width: '14px', height: '14px', color: '#6B7280' }} />
                  </button>
                  <span style={{ fontSize: '12px', color: '#6B7280', minWidth: '40px', textAlign: 'center' }}>
                    {page + 1}/{totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="flex items-center p-1 rounded hover:bg-[#F3F4F6] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ background: 'none', border: 'none', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer' }}
                  >
                    <ChevronRight style={{ width: '14px', height: '14px', color: '#6B7280' }} />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Side panel with backdrop (company mode only) */}
      {selectedItem && !isContactMode && (
        <>
          <div
            className="fixed inset-0 z-30"
            style={{ background: 'rgba(0,0,0,0.1)' }}
            onClick={() => setSelectedItem(null)}
          />
          <PipelineSidePanel
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
            onOpenProfile={handleOpenProfile}
          />
        </>
      )}

      {selectedContact && isContactMode && (
        <>
          <div
            className="fixed inset-0 z-30"
            style={{ background: 'rgba(0,0,0,0.1)' }}
            onClick={() => setSelectedContact(null)}
          />
          <ContactDetailPanel
            contact={selectedContact}
            onClose={() => setSelectedContact(null)}
          />
        </>
      )}
    </div>
  )
}
