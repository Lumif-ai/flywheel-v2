import { useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { gridTheme, GRID_SHADOW, GRID_BORDER_RADIUS } from '@/shared/grid/theme'
import { CurrencyCell, ClauseLink } from '@/shared/grid/cell-renderers'
import type { ProjectCoverage } from '../types/broker'

const INSURANCE_CATEGORIES = ['liability', 'property', 'auto', 'workers_comp', 'specialty']
const SURETY_CATEGORIES = ['surety']

type SectionHeaderRow = { _type: 'section-header'; label: string }
type GridRow = ProjectCoverage | SectionHeaderRow

function isSectionHeader(row: GridRow): row is SectionHeaderRow {
  return (row as SectionHeaderRow)._type === 'section-header'
}

function SectionHeaderRenderer(props: ICellRendererParams) {
  const row = props.data as SectionHeaderRow
  return (
    <div
      className="flex items-center h-full px-4"
      style={{ background: '#F9FAFB' }}
    >
      <span className="text-sm font-medium text-muted-foreground">{row?.label}</span>
    </div>
  )
}

function GapAmountCell(props: ICellRendererParams) {
  const cov = props.data as ProjectCoverage & { _type?: string }
  if (!cov || cov._type === 'section-header') return null

  const amount =
    cov.gap_status === 'missing'
      ? (cov.gap_amount ?? cov.required_limit)
      : cov.gap_status === 'insufficient'
        ? (cov.gap_amount ??
          (cov.required_limit != null && cov.current_limit != null
            ? cov.required_limit - cov.current_limit
            : null))
        : null

  if (amount == null) {
    return (
      <div className="flex items-center justify-end h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)

  const isUrgent = cov.gap_status === 'missing' || cov.gap_status === 'insufficient'

  return (
    <div className="flex items-center justify-end h-full">
      <span
        className={isUrgent ? 'font-medium' : ''}
        style={isUrgent ? { color: '#DC2626', fontFeatureSettings: '"tnum"' } : { fontFeatureSettings: '"tnum"' }}
      >
        {formatted}
      </span>
    </div>
  )
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  missing: { bg: '#FEE2E2', text: '#B91C1C' },
  insufficient: { bg: '#FEF3C7', text: '#A16207' },
  covered: { bg: '#DCFCE7', text: '#15803D' },
  unknown: { bg: '#F3F4F6', text: '#6B7280' },
}

function GapStatusCell(props: ICellRendererParams) {
  const cov = props.data as ProjectCoverage & { _type?: string }
  if (!cov || cov._type === 'section-header') return null

  const status = cov.gap_status ?? 'unknown'
  const colors = STATUS_COLORS[status.toLowerCase()] ?? STATUS_COLORS.unknown

  return (
    <div className="flex items-center h-full">
      <span
        style={{
          backgroundColor: colors.bg,
          color: colors.text,
          padding: '2px 8px',
          borderRadius: 9999,
          fontSize: 12,
          fontWeight: 500,
          textTransform: 'capitalize',
        }}
      >
        {status.replace('_', ' ')}
      </span>
    </div>
  )
}

interface GapCoverageGridProps {
  coverages: ProjectCoverage[]
}

export function GapCoverageGrid({ coverages }: GapCoverageGridProps) {
  const insuranceCoverages = useMemo(() => {
    const insurance = coverages.filter((c) => INSURANCE_CATEGORIES.includes(c.category))
    const other = coverages.filter(
      (c) =>
        !INSURANCE_CATEGORIES.includes(c.category) && !SURETY_CATEGORIES.includes(c.category),
    )
    return [...insurance, ...other]
  }, [coverages])

  const suretyCoverages = useMemo(
    () => coverages.filter((c) => SURETY_CATEGORIES.includes(c.category)),
    [coverages],
  )

  const rowData = useMemo<GridRow[]>(() => {
    const rows: GridRow[] = []
    if (insuranceCoverages.length > 0) {
      rows.push({ _type: 'section-header', label: 'Insurance Coverages' })
      rows.push(...insuranceCoverages)
    }
    if (suretyCoverages.length > 0) {
      rows.push({ _type: 'section-header', label: 'Surety Bonds' })
      rows.push(...suretyCoverages)
    }
    return rows
  }, [insuranceCoverages, suretyCoverages])

  const columnDefs = useMemo<ColDef<GridRow>[]>(
    () => [
      {
        headerName: 'Coverage',
        flex: 2,
        minWidth: 160,
        valueGetter: (p) =>
          p.data && isSectionHeader(p.data) ? '' : (p.data as ProjectCoverage)?.coverage_type ?? '',
      },
      {
        field: 'required_limit' as keyof GridRow,
        headerName: 'Required Limit',
        flex: 1,
        minWidth: 120,
        cellRenderer: CurrencyCell,
      },
      {
        field: 'current_limit' as keyof GridRow,
        headerName: 'Current Limit',
        flex: 1,
        minWidth: 120,
        cellRenderer: CurrencyCell,
      },
      {
        headerName: 'Gap Amount',
        flex: 1,
        minWidth: 120,
        cellRenderer: GapAmountCell,
      },
      {
        field: 'contract_clause' as keyof GridRow,
        headerName: 'Contract Clause',
        flex: 2,
        minWidth: 160,
        cellRenderer: ClauseLink,
      },
      {
        headerName: 'Status',
        flex: 1,
        minWidth: 100,
        cellRenderer: GapStatusCell,
      },
    ],
    [],
  )

  const gridHeight = Math.min(rowData.length * 44 + 36, 600)

  return (
    <div
      style={{
        height: gridHeight,
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
        domLayout="normal"
        defaultColDef={{ resizable: true, sortable: false }}
        suppressMovableColumns
        headerHeight={36}
        rowHeight={44}
        isFullWidthRow={(params) =>
          (params.rowNode.data as SectionHeaderRow | undefined)?._type === 'section-header'
        }
        fullWidthCellRenderer={SectionHeaderRenderer}
        getRowStyle={(params) => {
          const row = params.data as GridRow | undefined
          if (!row) return undefined
          if (isSectionHeader(row)) return { background: '#F9FAFB', border: 'none' as const }
          const cov = row as ProjectCoverage
          if (cov.gap_status === 'missing') return { background: 'rgba(239,68,68,0.06)', border: 'none' as const }
          if (cov.gap_status === 'insufficient') return { background: 'rgba(245,158,11,0.06)', border: 'none' as const }
          return undefined
        }}
      />
    </div>
  )
}
