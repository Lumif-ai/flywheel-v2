import type { ColDef } from 'ag-grid-community'
import { NameCell } from '../components/cell-renderers/NameCell'
import { ContactCell } from '../components/cell-renderers/ContactCell'
import { StagePill } from '../components/cell-renderers/StagePill'
import { FitTierBadge } from '../components/cell-renderers/FitTierBadge'
import { ChannelsCell } from '../components/cell-renderers/ChannelsCell'
import { AiInsightCell } from '../components/cell-renderers/AiInsightCell'
import { OutreachStatusCell } from '../components/cell-renderers/OutreachStatusCell'
import { DateCell, DatePickerEditor, ExpandToggleCell } from '@/shared/grid/cell-renderers'
import { useColumnPersistence } from '@/shared/grid/useColumnPersistence'
import type { PipelineListItem } from '../types/pipeline'

const columnDefs: ColDef<PipelineListItem>[] = [
  // 0. Expand toggle — pinned left
  {
    headerName: '',
    colId: 'expand',
    width: 40,
    minWidth: 40,
    maxWidth: 40,
    pinned: 'left',
    sortable: false,
    resizable: false,
    suppressMovable: true,
    lockPosition: 'left',
    cellRenderer: ExpandToggleCell,
    // cellRendererParams overridden in PipelinePage.tsx
  },
  // 1. Row number — pinned left
  {
    headerName: '',
    width: 48,
    pinned: 'left',
    sortable: false,
    resizable: false,
    suppressMovable: true,
    lockPosition: 'left',
    cellStyle: { color: '#9CA3AF', fontSize: '11px', textAlign: 'center' },
    valueGetter: (params) => (params.node ? params.node.rowIndex! + 1 : ''),
  },
  // 2. Name (widened, domain shown as icon)
  {
    headerName: 'Name',
    field: 'name',
    width: 260,
    pinned: 'left',
    cellRenderer: NameCell,
    editable: false,
    sortable: true,
  },
  // 3. Primary Contact
  {
    headerName: 'Primary Contact',
    field: 'primary_contact' as keyof PipelineListItem,
    width: 160,
    cellRenderer: ContactCell,
    editable: false,
    sortable: false,
  },
  // 4. Stage — editable dropdown
  {
    headerName: 'Stage',
    field: 'stage',
    width: 130,
    cellRenderer: StagePill,
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['identified', 'contacted', 'engaged', 'qualified', 'committed', 'closed'],
    },
    sortable: true,
  },
  // 5. Fit — editable dropdown
  {
    headerName: 'Fit',
    field: 'fit_tier',
    width: 100,
    cellRenderer: FitTierBadge,
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Strong', 'Medium', 'Weak'],
    },
    sortable: true,
  },
  // 6. Channels
  {
    headerName: 'Channels',
    field: 'channels',
    width: 120,
    cellRenderer: ChannelsCell,
    editable: false,
    sortable: false,
  },
  // 7. Outreach (replaces Next Outreach)
  {
    headerName: 'Outreach',
    field: 'outreach_summary' as keyof PipelineListItem,
    width: 130,
    cellRenderer: OutreachStatusCell,
    editable: false,
    sortable: false,
  },
  // 8. AI Insight
  {
    headerName: 'AI Insight',
    field: 'ai_summary',
    width: 200,
    cellRenderer: AiInsightCell,
    editable: false,
    sortable: false,
  },
  // 9. Next Action — editable date picker
  {
    headerName: 'Next Action',
    field: 'next_action_date',
    width: 150,
    cellRenderer: DateCell,
    editable: true,
    cellEditor: DatePickerEditor,
    sortable: true,
  },
]

export function usePipelineColumns() {
  const { restoreColumnState, onColumnStateChanged, gridApiRef } =
    useColumnPersistence('pipeline-col-state')

  return {
    columnDefs,
    restoreColumnState,
    onColumnStateChanged,
    gridApiRef,
  }
}
