import { useMemo, useState, useCallback } from 'react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, ICellRendererParams, IHeaderParams, IsFullWidthRowParams } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { gridTheme } from '@/shared/grid/theme'
import type { ComparisonCoverage, ComparisonQuoteCell } from '../../types/broker'
import { INSURANCE_CATEGORIES, SURETY_CATEGORIES } from './comparison-utils'

interface ComparisonGridProps {
  coverages: ComparisonCoverage[]
  selectedCarriers: Set<string>
  currency: string
  highlightBest: boolean
  viewMode?: 'interactive' | 'pdf'
}

// ---- Carrier header with optional Recommended badge ----
function CarrierHeaderWithBadge(props: IHeaderParams & { isRecommended?: boolean }) {
  return (
    <div className="flex items-center gap-2 h-full">
      <span>{props.displayName}</span>
      {props.isRecommended && (
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full shrink-0"
          style={{ background: '#E94D35', color: 'white' }}
        >
          Recommended
        </span>
      )}
    </div>
  )
}

// ---- Section header full-width renderer with collapse toggle ----
interface SectionHeaderRendererParams extends ICellRendererParams {
  onToggleSection?: (label: string) => void
  collapsedSections?: Set<string>
}

function SectionHeaderRenderer(props: SectionHeaderRendererParams) {
  const label = (props.data as SectionHeaderRow).label
  const ctx = props.context as { onToggleSection?: (l: string) => void; collapsedSections?: Set<string> } | undefined
  const isCollapsed = ctx?.collapsedSections?.has(label) ?? false
  const Icon = isCollapsed ? ChevronRight : ChevronDown

  return (
    <button
      type="button"
      className="flex items-center gap-2 h-full w-full px-4 bg-gray-50 border-b border-t border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors"
      onClick={() => ctx?.onToggleSection?.(label)}
    >
      <Icon className="h-4 w-4 text-gray-400 shrink-0" />
      <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</span>
    </button>
  )
}

// ---- Unified cell renderer — handles data cells AND pinned totals row ----
function CarrierCellRenderer(props: ICellRendererParams) {
  const currency = (props.context as { currency: string } | undefined)?.currency ?? 'USD'

  // Pinned bottom row: show total premium
  if (props.node.rowPinned === 'bottom') {
    const value = props.value as number | undefined
    if (props.colDef?.field === 'coverage_type' || value == null) {
      return (
        <div className="flex items-center h-full px-1">
          <span className="font-semibold text-sm text-gray-700">Total Premium</span>
        </div>
      )
    }
    const fmtTotal = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(value as number)
    return (
      <div className="flex items-center justify-end h-full px-1">
        <span className="font-semibold text-sm">{fmtTotal}</span>
      </div>
    )
  }

  // Regular data cell
  const cell = props.value as ComparisonQuoteCell | undefined
  if (!cell) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-muted-foreground text-sm">—</span>
      </div>
    )
  }

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

// ---- Row type discriminators ----
type SectionHeaderRow = { _type: 'section-header'; label: string; coverage_type: string }
type CoverageRow = { _type: 'coverage'; coverage_type: string; _section?: string; [carrierName: string]: unknown }
type GridRow = SectionHeaderRow | CoverageRow

function isFullWidthRowFn(params: IsFullWidthRowParams<GridRow>): boolean {
  return params.rowNode.data?._type === 'section-header'
}

export function findRecommendedCarrier(coverages: ComparisonCoverage[]): string | null {
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

// ---- PDF print view ----
function PdfPrintView({
  coverages,
  carriers,
  currency,
  recommendedCarrier,
}: {
  coverages: ComparisonCoverage[]
  carriers: string[]
  currency: string
  recommendedCarrier: string | null
}) {
  const fmt = (v: number | null) =>
    v == null
      ? '—'
      : new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(v)

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-4 py-3 font-semibold text-gray-700 w-40">Coverage</th>
            {carriers.map((c) => (
              <th
                key={c}
                className="text-left px-4 py-3 font-semibold text-gray-700"
                style={c === recommendedCarrier ? { borderLeft: '3px solid #E94D35' } : undefined}
              >
                <div className="flex items-center gap-2">
                  {c}
                  {c === recommendedCarrier && (
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ background: '#E94D35', color: 'white' }}
                    >
                      Recommended
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {coverages.map((cov) => (
            <tr key={cov.coverage_id} className="border-b border-gray-100">
              <td className="px-4 py-3 text-gray-700 font-medium">{cov.coverage_type}</td>
              {carriers.map((c) => {
                const q = cov.quotes.find((q) => q.carrier_name === c)
                return (
                  <td
                    key={c}
                    className="px-4 py-3"
                    style={c === recommendedCarrier ? { borderLeft: '3px solid #E94D35' } : undefined}
                  >
                    {q ? (
                      <div>
                        <div className="font-medium">{fmt(q.premium)}</div>
                        <div className="text-xs text-gray-500">
                          {q.limit_amount != null ? fmt(q.limit_amount) : ''}
                          {q.deductible != null ? ` / Ded: ${fmt(q.deductible)}` : ''}
                        </div>
                      </div>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-gray-50 border-t border-gray-200">
            <td className="px-4 py-3 font-semibold text-gray-700">Total Premium</td>
            {carriers.map((c) => {
              const total = coverages.reduce((sum, cov) => {
                const q = cov.quotes.find((q) => q.carrier_name === c)
                return sum + (q?.premium ?? 0)
              }, 0)
              return (
                <td
                  key={c}
                  className="px-4 py-3 font-semibold"
                  style={c === recommendedCarrier ? { borderLeft: '3px solid #E94D35' } : undefined}
                >
                  {fmt(total)}
                </td>
              )
            })}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export function ComparisonGrid({
  coverages,
  selectedCarriers,
  currency,
  highlightBest,
  viewMode = 'interactive',
}: ComparisonGridProps) {
  const carriers = useMemo(() => Array.from(selectedCarriers), [selectedCarriers])

  const recommendedCarrier = useMemo(
    () => (highlightBest ? findRecommendedCarrier(coverages) : null),
    [coverages, highlightBest]
  )

  // ---- Expandable groups state ----
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set())

  const toggleSection = useCallback((label: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev)
      if (next.has(label)) {
        next.delete(label)
      } else {
        next.add(label)
      }
      return next
    })
  }, [])

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
      cellRenderer: CarrierCellRenderer,
      headerComponent: CarrierHeaderWithBadge,
      headerComponentParams: {
        isRecommended: highlightBest && carrierName === recommendedCarrier,
      },
      cellStyle:
        highlightBest && carrierName === recommendedCarrier
          ? { borderLeft: '3px solid #E94D35' }
          : undefined,
    }))

    return [coverageCol, ...carrierCols]
  }, [carriers, highlightBest, recommendedCarrier])

  // ---- Build rowData with section tracking (for collapse filtering) ----
  const allRowsWithSections = useMemo<GridRow[]>(() => {
    const rows: GridRow[] = []

    const insuranceCoverages = coverages.filter((c) => INSURANCE_CATEGORIES.includes(c.category))
    const suretyCoverages = coverages.filter((c) => SURETY_CATEGORIES.includes(c.category))
    const otherCoverages = coverages.filter(
      (c) => !INSURANCE_CATEGORIES.includes(c.category) && !SURETY_CATEGORIES.includes(c.category)
    )

    const addSection = (label: string, sectionCoverages: ComparisonCoverage[]) => {
      if (sectionCoverages.length === 0) return
      rows.push({ _type: 'section-header', label, coverage_type: label })
      for (const cov of sectionCoverages) {
        const row: CoverageRow = {
          _type: 'coverage',
          coverage_type: cov.coverage_type,
          _section: label,
        }
        for (const carrierName of carriers) {
          row[carrierName] = cov.quotes.find((q) => q.carrier_name === carrierName)
        }
        rows.push(row)
      }
    }

    addSection('Insurance Coverages', insuranceCoverages)
    addSection('Surety Bonds', suretyCoverages)
    addSection('Other', otherCoverages)

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

  // ---- Filter rows based on collapsed sections ----
  const rowData = useMemo<GridRow[]>(() => {
    if (collapsedSections.size === 0) return allRowsWithSections
    return allRowsWithSections.filter((row) => {
      if (row._type === 'section-header') return true
      const section = (row as CoverageRow)._section
      return !section || !collapsedSections.has(section)
    })
  }, [allRowsWithSections, collapsedSections])

  // ---- Pinned totals — always computed from FULL coverages (not filtered rows) ----
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

  // ---- PDF mode: static print-friendly table ----
  if (viewMode === 'pdf') {
    return (
      <PdfPrintView
        coverages={coverages}
        carriers={carriers}
        currency={currency}
        recommendedCarrier={recommendedCarrier}
      />
    )
  }

  const gridHeight = Math.min(Math.max(rowData.length * 50 + 36, 200), 700)

  // Context carries currency + section toggle state to full-width cell renderer
  const gridContext = useMemo(
    () => ({ currency, onToggleSection: toggleSection, collapsedSections }),
    [currency, toggleSection, collapsedSections]
  )

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <div style={{ height: gridHeight }}>
        <AgGridReact<GridRow>
          modules={[AllCommunityModule]}
          theme={gridTheme}
          rowData={rowData}
          columnDefs={colDefs}
          pinnedBottomRowData={pinnedBottomRowData}
          context={gridContext}
          isFullWidthRow={isFullWidthRowFn}
          fullWidthCellRenderer={SectionHeaderRenderer}
          defaultColDef={{ resizable: true, sortable: false }}
          rowHeight={50}
          headerHeight={36}
        />
      </div>
    </div>
  )
}
