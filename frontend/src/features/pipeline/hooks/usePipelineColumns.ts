import { useCallback, useRef } from 'react'
import type { ColDef, GridApi, ColumnState } from 'ag-grid-community'
import { CompanyCell } from '../components/cell-renderers/CompanyCell'
import { ContactCell } from '../components/cell-renderers/ContactCell'
import { FitTierBadge } from '../components/cell-renderers/FitTierBadge'
import { OutreachDot } from '../components/cell-renderers/OutreachDot'
import { GraduateButton } from '../components/cell-renderers/GraduateButton'
import { DaysSinceCell } from '../components/cell-renderers/DaysSinceCell'
import type { PipelineItem } from '../types/pipeline'

const COLUMN_STATE_KEY = 'flywheel:pipeline:columnState'

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never'
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const columnDefs: ColDef<PipelineItem>[] = [
  {
    headerName: 'Company',
    field: 'name',
    cellRenderer: CompanyCell,
    minWidth: 200,
    flex: 1.5,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Contact',
    field: 'primary_contact_name',
    cellRenderer: ContactCell,
    minWidth: 160,
    flex: 1,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Email',
    field: 'primary_contact_email',
    minWidth: 140,
    resizable: true,
    sortable: false,
    cellRenderer: (params: { value: string | null | undefined }) => {
      if (!params.value) return '<span style="color:var(--secondary-text)">—</span>'
      return `<a href="mailto:${params.value}" style="color:var(--brand-coral);font-size:13px;text-decoration:none;">${params.value}</a>`
    },
  },
  {
    headerName: 'LinkedIn',
    field: 'primary_contact_linkedin',
    minWidth: 80,
    width: 80,
    resizable: true,
    sortable: false,
    cellRenderer: (params: { value: string | null | undefined }) => {
      if (!params.value) return '<span style="color:var(--secondary-text)">—</span>'
      return `<a href="${params.value}" target="_blank" rel="noreferrer" style="color:var(--brand-coral);font-size:13px;">↗</a>`
    },
  },
  {
    headerName: 'Fit Tier',
    field: 'fit_tier',
    cellRenderer: FitTierBadge,
    width: 120,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Outreach',
    field: 'last_outreach_status',
    cellRenderer: OutreachDot,
    width: 130,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Last Action',
    field: 'last_interaction_at',
    width: 140,
    resizable: true,
    sortable: true,
    valueFormatter: (params) => formatRelativeTime(params.value as string | null),
  },
  {
    headerName: 'Days Stale',
    field: 'days_since_last_outreach',
    width: 100,
    resizable: true,
    sortable: true,
    cellRenderer: DaysSinceCell,
  },
  {
    headerName: 'Graduate',
    field: undefined,
    cellRenderer: GraduateButton,
    width: 110,
    sortable: false,
    resizable: false,
    pinned: 'right' as const,
    suppressMovable: true,
  },
]

export function usePipelineColumns() {
  const gridApiRef = useRef<GridApi | null>(null)

  const getInitialState = (): { columnState: ColumnState[] } | undefined => {
    try {
      const raw = localStorage.getItem(COLUMN_STATE_KEY)
      if (!raw) return undefined
      const parsed = JSON.parse(raw) as ColumnState[]
      return { columnState: parsed }
    } catch {
      return undefined
    }
  }

  const onColumnStateChanged = useCallback(() => {
    const api = gridApiRef.current
    if (!api) return
    try {
      const state = api.getColumnState()
      localStorage.setItem(COLUMN_STATE_KEY, JSON.stringify(state))
    } catch {
      // localStorage write failure — non-fatal
    }
  }, [])

  return {
    columnDefs,
    initialState: getInitialState(),
    onColumnStateChanged,
    gridApiRef,
  }
}
