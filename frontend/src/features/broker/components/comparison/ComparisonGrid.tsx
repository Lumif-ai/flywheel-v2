import { useMemo } from 'react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, ICellRendererParams, IsFullWidthRowParams } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { gridTheme } from '@/shared/grid/theme'
import type { ComparisonCoverage, ComparisonQuoteCell } from '../../types/broker'
import { INSURANCE_CATEGORIES, SURETY_CATEGORIES } from './comparison-utils'

interface ComparisonGridProps {
  coverages: ComparisonCoverage[]
  selectedCarriers: Set<string>
  currency: string
  highlightBest: boolean
}

// ---- Section header full-width renderer ----
function SectionHeaderRenderer(props: ICellRendererParams) {
  const label = (props.data as SectionHeaderRow).label
  return (
    <div className="flex items-center h-full px-4 bg-gray-50 border-b border-t border-gray-200">
      <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</span>
    </div>
  )
}

// ---- Comparison cell renderer ----
function ComparisonCellRenderer(props: ICellRendererParams) {
  const cell = props.value as ComparisonQuoteCell | undefined
  if (!cell) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-muted-foreground text-sm">—</span>
      </div>
    )
  }
  const currency = (props.context as { currency: string } | undefined)?.currency ?? 'USD'
  const fmt = (v: number | null) =>
    v == null
      ? '—'
      : new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency,
          maximumFractionDigits: 0,
        }).format(v)

  const isCritical = cell.has_critical_exclusion
  const isRec = cell.is_recommended

  return (
    <div
      className={`h-full flex flex-col justify-center px-1 ${
        isCritical ? 'bg-red-50' : isRec ? 'bg-green-50' : ''
      }`}
    >
      <div className="font-medium text-sm">{fmt(cell.premium)}</div>
      <div className="text-xs text-muted-foreground">
        {cell.limit_amount != null ? fmt(cell.limit_amount) : ''}
        {cell.deductible != null ? ` / Ded: ${fmt(cell.deductible)}` : ''}
      </div>
    </div>
  )
}

// ---- Totals cell renderer ----
function TotalsCellRenderer(props: ICellRendererParams) {
  const value = props.value as number | undefined
  if (value == null || props.colDef?.field === 'coverage_type') {
    return (
      <div className="flex items-center h-full px-1">
        <span className="font-semibold text-sm text-gray-700">Total Premium</span>
      </div>
    )
  }
  const currency = (props.context as { currency: string } | undefined)?.currency ?? 'USD'
  const fmt = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value)
  return (
    <div className="flex items-center justify-end h-full px-1">
      <span className="font-semibold text-sm">{fmt}</span>
    </div>
  )
}

// ---- Row type discriminators ----
type SectionHeaderRow = { _type: 'section-header'; label: string; coverage_type: string }
type CoverageRow = { _type: 'coverage'; coverage_type: string; [carrierName: string]: unknown }
type GridRow = SectionHeaderRow | CoverageRow

function isFullWidthRowFn(params: IsFullWidthRowParams<GridRow>): boolean {
  return params.rowNode.data?._type === 'section-header'
}

function findRecommendedCarrier(coverages: ComparisonCoverage[]): string | null {
  const counts: Record<string, number> = {}
  for (const cov of coverages) {
    for (const q of cov.quotes) {
      if (q.is_recommended) {
        counts[q.carrier_name] = (counts[q.carrier_name] ?? 0) + 1
      }
    }
  }
  const entries = Object.entries(counts)
  if (!entries.length) return null
  return entries.reduce((a, b) => (a[1] >= b[1] ? a : b))[0]
}

export function ComparisonGrid({
  coverages,
  selectedCarriers,
  currency,
  highlightBest,
}: ComparisonGridProps) {
  const carriers = useMemo(
    () => Array.from(selectedCarriers),
    [selectedCarriers]
  )

  const recommendedCarrier = useMemo(
    () => (highlightBest ? findRecommendedCarrier(coverages) : null),
    [coverages, highlightBest]
  )

  const colDefs = useMemo<ColDef<GridRow>[]>(() => {
    const coverageCol: ColDef<GridRow> = {
      field: 'coverage_type',
      headerName: 'Coverage',
      pinned: 'left' as const,
      width: 180,
      sortable: false,
      resizable: true,
    }

    const carrierCols: ColDef<GridRow>[] = carriers.map((carrierName) => ({
      field: carrierName,
      headerName: carrierName,
      flex: 1,
      minWidth: 160,
      sortable: false,
      resizable: true,
      cellRenderer: ComparisonCellRenderer,
      cellStyle:
        highlightBest && carrierName === recommendedCarrier
          ? { borderLeft: '3px solid #E94D35' }
          : undefined,
    }))

    return [coverageCol, ...carrierCols]
  }, [carriers, highlightBest, recommendedCarrier])

  const rowData = useMemo<GridRow[]>(() => {
    const rows: GridRow[] = []

    const insuranceCoverages = coverages.filter((c) =>
      INSURANCE_CATEGORIES.includes(c.category)
    )
    const suretyCoverages = coverages.filter((c) =>
      SURETY_CATEGORIES.includes(c.category)
    )
    const otherCoverages = coverages.filter(
      (c) =>
        !INSURANCE_CATEGORIES.includes(c.category) &&
        !SURETY_CATEGORIES.includes(c.category)
    )

    const addSection = (label: string, sectionCoverages: ComparisonCoverage[]) => {
      if (sectionCoverages.length === 0) return
      rows.push({
        _type: 'section-header',
        label,
        coverage_type: label,
      })
      for (const cov of sectionCoverages) {
        const row: CoverageRow = {
          _type: 'coverage',
          coverage_type: cov.coverage_type,
        }
        for (const carrierName of carriers) {
          row[carrierName] = cov.quotes.find((q) => q.carrier_name === carrierName)
        }
        rows.push(row)
      }
    }

    if (insuranceCoverages.length > 0) {
      addSection('Insurance Coverages', insuranceCoverages)
    }
    if (suretyCoverages.length > 0) {
      addSection('Surety Bonds', suretyCoverages)
    }
    if (otherCoverages.length > 0) {
      addSection('Other', otherCoverages)
    }

    // Fallback: if no category separation happened, add all without section headers
    if (rows.length === 0) {
      for (const cov of coverages) {
        const row: CoverageRow = {
          _type: 'coverage',
          coverage_type: cov.coverage_type,
        }
        for (const carrierName of carriers) {
          row[carrierName] = cov.quotes.find((q) => q.carrier_name === carrierName)
        }
        rows.push(row)
      }
    }

    return rows
  }, [coverages, carriers])

  const pinnedBottomRowData = useMemo(() => {
    const totalsRow: Record<string, unknown> = { coverage_type: 'Total Premium' }
    for (const carrierName of carriers) {
      totalsRow[carrierName] = coverages.reduce((sum, cov) => {
        const q = cov.quotes.find((q) => q.carrier_name === carrierName)
        return sum + (q?.premium ?? 0)
      }, 0)
    }
    return [totalsRow]
  }, [coverages, carriers])

  if (coverages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
        No coverage data available
      </div>
    )
  }

  const gridHeight = Math.min(Math.max(rowData.length * 50 + 36, 200), 700)

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <div style={{ height: gridHeight }}>
        <AgGridReact<GridRow>
          modules={[AllCommunityModule]}
          theme={gridTheme}
          rowData={rowData}
          columnDefs={colDefs}
          pinnedBottomRowData={pinnedBottomRowData}
          context={{ currency }}
          isFullWidthRow={isFullWidthRowFn}
          fullWidthCellRenderer={SectionHeaderRenderer}
          defaultColDef={{ resizable: true, sortable: false }}
          rowHeight={50}
          headerHeight={36}
          pinnedBottomRowCellRenderer={TotalsCellRenderer}
        />
      </div>
    </div>
  )
}
