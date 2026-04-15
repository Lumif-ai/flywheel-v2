import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Mail, Globe } from 'lucide-react'
import { gridTheme, GRID_SHADOW, GRID_BORDER_RADIUS } from '@/shared/grid/theme'
import { CarrierCell } from '@/shared/grid/cell-renderers/CarrierCell'
import { useCarrierMatches } from '../hooks/useCarrierMatches'
import { useDraftSolicitations } from '../hooks/useSolicitations'
import type { CarrierMatch } from '../types/broker'

interface CarrierSelectionProps {
  projectId: string
}

type SectionHeaderRow = { _type: 'section-header'; label: string }
type GridRow = CarrierMatch | SectionHeaderRow

function isSectionHeader(row: GridRow): row is SectionHeaderRow {
  return (row as SectionHeaderRow)._type === 'section-header'
}

function SectionHeaderRenderer(props: ICellRendererParams) {
  const row = props.data as SectionHeaderRow
  return (
    <div className="px-3 py-1 flex items-center h-full">
      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {row?.label}
      </span>
    </div>
  )
}

function MethodCell(props: ICellRendererParams) {
  const row = props.data as GridRow
  if (!row || isSectionHeader(row)) return null
  const method = (row as CarrierMatch).submission_method
  return (
    <div className="flex items-center h-full">
      <Badge variant="outline" className="text-xs gap-1">
        {method === 'portal' ? (
          <><Globe className="h-3 w-3" /> Portal</>
        ) : (
          <><Mail className="h-3 w-3" /> Email</>
        )}
      </Badge>
    </div>
  )
}

function RoutingRuleCell(props: ICellRendererParams) {
  const row = props.data as GridRow
  if (!row || isSectionHeader(row)) return null
  const carrier = row as CarrierMatch
  const matched = carrier.matched_coverages?.length > 0
  return (
    <div className="flex items-center h-full">
      {matched ? (
        <span className="text-xs font-medium" style={{ color: '#15803D' }}>&#10003; Matched</span>
      ) : (
        <span className="text-xs text-muted-foreground">&mdash;</span>
      )}
    </div>
  )
}

function AvgResponseCell(props: ICellRendererParams) {
  const row = props.data as GridRow
  if (!row || isSectionHeader(row)) return null
  const value = (row as CarrierMatch).avg_response_days
  return (
    <div className="flex items-center h-full">
      <span className="text-sm text-muted-foreground">
        {value != null ? `${value}d` : '—'}
      </span>
    </div>
  )
}

export function CarrierSelection({ projectId }: CarrierSelectionProps) {
  const { data, isLoading } = useCarrierMatches(projectId)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const draftMutation = useDraftSolicitations(projectId)
  const [skipped, setSkipped] = useState<Array<{ carrier: string; reason: string }>>([])

  const rowData = useMemo<GridRow[]>(() => {
    if (!data) return []
    const insuranceMatches = data.matches.filter((m) => m.carrier_type === 'insurance')
    const suretyMatches = data.matches.filter((m) => m.carrier_type === 'surety')
    const rows: GridRow[] = []
    if (insuranceMatches.length > 0) {
      rows.push({ _type: 'section-header', label: 'Insurance Carriers' })
      rows.push(...insuranceMatches)
    }
    if (suretyMatches.length > 0) {
      rows.push({ _type: 'section-header', label: 'Surety Carriers' })
      rows.push(...suretyMatches)
    }
    return rows
  }, [data])

  const columnDefs = useMemo<ColDef<GridRow>[]>(
    () => [
      {
        checkboxSelection: (params) => !isSectionHeader(params.data as GridRow),
        headerCheckboxSelection: true,
        width: 40,
        resizable: false,
        sortable: false,
        suppressHeaderMenuButton: true,
      },
      {
        field: 'carrier_name' as keyof GridRow,
        headerName: 'Carrier',
        flex: 2,
        cellRenderer: CarrierCell,
      },
      {
        field: 'submission_method' as keyof GridRow,
        headerName: 'Method',
        width: 120,
        cellRenderer: MethodCell,
      },
      {
        headerName: 'Routing Rule',
        width: 140,
        cellRenderer: RoutingRuleCell,
      },
      {
        field: 'avg_response_days' as keyof GridRow,
        headerName: 'Avg Response',
        width: 120,
        cellRenderer: AvgResponseCell,
      },
    ],
    [],
  )

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[52px] w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!data || data.matches.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center space-y-2">
        <p className="text-muted-foreground">
          No carriers configured. Go to{' '}
          <Link to="/broker/carriers" className="text-blue-600 hover:underline">
            Carriers
          </Link>{' '}
          to add your first carrier.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Carrier Matches</h3>

      <div
        style={{
          borderRadius: GRID_BORDER_RADIUS,
          boxShadow: GRID_SHADOW,
          overflow: 'hidden',
        }}
      >
        <AgGridReact<GridRow>
          modules={[AllCommunityModule]}
          theme={gridTheme}
          rowData={rowData}
          columnDefs={columnDefs}
          domLayout="autoHeight"
          rowSelection="multiple"
          suppressRowClickSelection
          suppressMovableColumns
          defaultColDef={{ resizable: true, sortable: false }}
          isFullWidthRow={(params) =>
            (params.rowNode.data as SectionHeaderRow | undefined)?._type === 'section-header'
          }
          fullWidthCellRenderer={SectionHeaderRenderer}
          getRowHeight={(params) =>
            isSectionHeader(params.data as GridRow) ? 32 : 52
          }
          onSelectionChanged={(event) => {
            const selected = event.api.getSelectedRows().filter(
              (r: GridRow) => !isSectionHeader(r),
            )
            setSelectedIds(new Set((selected as CarrierMatch[]).map((r) => r.carrier_config_id)))
          }}
        />
      </div>

      {skipped.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">Some carriers were skipped:</p>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {skipped.map((s, i) => (
              <li key={i}>{s.carrier}: {s.reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          disabled={selectedIds.size === 0 || draftMutation.isPending}
          onClick={() =>
            draftMutation.mutate(Array.from(selectedIds), {
              onSuccess: (resp) => {
                if (resp.skipped.length > 0) setSkipped(resp.skipped)
              },
            })
          }
        >
          {draftMutation.isPending
            ? 'Creating drafts...'
            : `Proceed to Solicitation${selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}`}
        </Button>
      </div>
    </div>
  )
}
