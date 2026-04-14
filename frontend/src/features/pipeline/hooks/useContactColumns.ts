import type { ColDef } from 'ag-grid-community'
import { NextStepCell } from '../components/cell-renderers/NextStepCell'
import { ContactStatusPill } from '../components/cell-renderers/ContactStatusPill'
import { ChannelIconsCell } from '../components/cell-renderers/ChannelIconsCell'
import { useColumnPersistence } from '@/shared/grid/useColumnPersistence'
import type { ContactListItem } from '../types/pipeline'

const columnDefs: ColDef<ContactListItem>[] = [
  // 1. Row number — pinned left
  {
    headerName: '#',
    width: 48,
    pinned: 'left',
    sortable: false,
    resizable: false,
    suppressMovable: true,
    lockPosition: 'left',
    cellStyle: { color: '#9CA3AF', fontSize: '11px', textAlign: 'center' },
    valueGetter: (params) => (params.node ? params.node.rowIndex! + 1 : ''),
  },
  // 2. Name — pinned left
  {
    headerName: 'Name',
    field: 'name',
    width: 180,
    pinned: 'left',
    sortable: true,
  },
  // 3. Company
  {
    headerName: 'Company',
    field: 'company_name',
    width: 160,
    sortable: true,
  },
  // 4. Campaign
  {
    headerName: 'Campaign',
    field: 'campaign',
    width: 200,
    sortable: false,
  },
  // 5. Source
  {
    headerName: 'Source',
    field: 'source',
    width: 130,
    sortable: false,
    cellStyle: { color: '#6B7280', fontSize: '12px' } as Record<string, string>,
  },
  // 6. Title
  {
    headerName: 'Title',
    field: 'title',
    width: 150,
    sortable: false,
  },
  // 5. Email
  {
    headerName: 'Email',
    field: 'email',
    width: 200,
    sortable: false,
  },
  // 6. Channels — icon per channel
  {
    headerName: 'Channel',
    width: 90,
    sortable: false,
    valueGetter: (params) => params.data?.channels ?? [],
    cellRenderer: ChannelIconsCell,
  },
  // 7. Variant
  {
    headerName: 'Variant',
    width: 220,
    sortable: false,
    valueGetter: (params) => {
      const v = params.data?.latest_activity?.variant
      const theme = params.data?.latest_activity?.variant_theme
      if (!v) return null
      return theme ? `${v} — ${theme}` : v
    },
  },
  // 8. Step
  {
    headerName: 'Step',
    width: 70,
    sortable: false,
    cellStyle: { textAlign: 'center' },
    valueGetter: (params) => params.data?.latest_activity?.step_number ?? null,
  },
  // 9. Status
  {
    headerName: 'Status',
    colId: 'contact_status',
    width: 110,
    sortable: true,
    valueGetter: (params) => params.data?.latest_activity?.status ?? null,
    cellRenderer: ContactStatusPill,
  },
  // 10. Last Action Date
  {
    headerName: 'Last Action',
    colId: 'occurred_at',
    width: 130,
    sortable: true,
    valueGetter: (params) => params.data?.latest_activity?.occurred_at ?? null,
    valueFormatter: (params) => {
      if (!params.value) return ''
      const d = new Date(params.value as string)
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    },
  },
  // 11. Next Step
  {
    headerName: 'Next Step',
    field: 'next_step',
    colId: 'next_step',
    width: 160,
    sortable: true,
    cellRenderer: NextStepCell,
  },
  // 12. Subject
  {
    headerName: 'Subject',
    width: 200,
    sortable: false,
    valueGetter: (params) => params.data?.latest_activity?.subject ?? null,
  },
]

export function useContactColumns() {
  const { restoreColumnState, onColumnStateChanged, gridApiRef } =
    useColumnPersistence('pipeline-contacts-col-state')

  return {
    columnDefs,
    restoreColumnState,
    onColumnStateChanged,
    gridApiRef,
  }
}
