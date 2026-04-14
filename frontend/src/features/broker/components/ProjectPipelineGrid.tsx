import { useCallback } from 'react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, GridApi } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { gridTheme } from '@/shared/grid/theme'
import { DateCell, StatusBadge, type StatusBadgeColors } from '@/shared/grid/cell-renderers'
import { useColumnPersistence } from '@/shared/grid/useColumnPersistence'
import type { BrokerProject } from '../types/broker'

export const BROKER_STATUS_COLORS: StatusBadgeColors = {
  new_request:     { bg: '#F3F4F6', text: '#374151' },
  analyzing:       { bg: '#DBEAFE', text: '#1D4ED8' },
  analysis_failed: { bg: '#FEE2E2', text: '#B91C1C' },
  gaps_identified: { bg: '#FEF3C7', text: '#A16207' },
  soliciting:      { bg: '#DBEAFE', text: '#1D4ED8' },
  quotes_partial:  { bg: '#CCFBF1', text: '#0F766E' },
  quotes_complete: { bg: '#DCFCE7', text: '#15803D' },
  recommended:     { bg: '#F3E8FF', text: '#7E22CE' },
  delivered:       { bg: '#DCFCE7', text: '#15803D' },
  bound:           { bg: '#DCFCE7', text: '#166534' },
  cancelled:       { bg: '#F3F4F6', text: '#9CA3AF' },
}

interface ProjectPipelineGridProps {
  projects: BrokerProject[]
  total: number
  isLoading: boolean
  offset: number
  limit: number
  onPageChange: (offset: number) => void
  onRowClick: (id: string) => void
  storageKey: string
}

const columnDefs: ColDef<BrokerProject>[] = [
  { field: 'name', headerName: 'Project Name', flex: 2, minWidth: 200 },
  { field: 'project_type', headerName: 'Type', flex: 1, minWidth: 100 },
  {
    field: 'status',
    headerName: 'Status',
    flex: 1,
    minWidth: 140,
    cellRenderer: StatusBadge,
    cellRendererParams: { colorMap: BROKER_STATUS_COLORS },
  },
  { field: 'created_at', headerName: 'Created', flex: 1, minWidth: 120, cellRenderer: DateCell },
  { field: 'updated_at', headerName: 'Updated', flex: 1, minWidth: 120, cellRenderer: DateCell },
]

export function ProjectPipelineGrid({
  projects,
  total,
  isLoading,
  offset,
  limit,
  onPageChange,
  onRowClick,
  storageKey,
}: ProjectPipelineGridProps) {
  const { restoreColumnState, onColumnStateChanged, gridApiRef } =
    useColumnPersistence(storageKey)

  const handleGridReady = useCallback(
    (e: { api: GridApi }) => {
      gridApiRef.current = e.api
      restoreColumnState(e.api)
    },
    [gridApiRef, restoreColumnState]
  )

  const start = offset + 1
  const end = Math.min(offset + limit, total)

  if (isLoading && projects.length === 0) {
    return (
      <div className="rounded-xl border bg-white shadow-sm flex items-center justify-center" style={{ height: 300 }}>
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <div style={{ height: Math.min(projects.length * 44 + 36, 500) }}>
        <AgGridReact<BrokerProject>
          modules={[AllCommunityModule]}
          theme={gridTheme}
          rowData={projects}
          columnDefs={columnDefs}
          getRowId={(params) => params.data.id}
          onGridReady={handleGridReady}
          onColumnResized={onColumnStateChanged}
          onColumnMoved={onColumnStateChanged}
          onColumnVisible={onColumnStateChanged}
          onRowClicked={(e) => {
            if (e.data) onRowClick(e.data.id)
          }}
          defaultColDef={{ resizable: true, sortable: true }}
          sortingOrder={['asc', 'desc', null]}
        />
      </div>

      {total > limit && (
        <div className="flex items-center justify-between border-t px-4 py-3">
          <span className="text-sm text-muted-foreground">
            {start}-{end} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => onPageChange(Math.max(0, offset - limit))}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + limit >= total}
              onClick={() => onPageChange(offset + limit)}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
