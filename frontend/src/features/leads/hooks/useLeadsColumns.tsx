import { useCallback, useRef } from 'react'
import type { ColDef, GridApi, ColumnState, ICellRendererParams, GridState } from 'ag-grid-community'
import { Mail, Linkedin } from 'lucide-react'
import { STAGE_COLORS } from '../types/lead'
import { badges } from '@/lib/design-tokens'
import type { LeadRow } from '../types/lead'

const COLUMN_STATE_KEY = 'flywheel:leads:columnState'

type FitTierKey = keyof typeof badges.fitTier

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getNextFollowUp(row: LeadRow): string | null {
  const drafted = row.messages.filter((m) => m.status === 'drafted' && m.metadata?.send_after)
  if (drafted.length === 0) return null
  drafted.sort((a, b) => (a.metadata.send_after! > b.metadata.send_after! ? 1 : -1))
  const due = new Date(drafted[0].metadata.send_after!)
  const now = new Date()
  const diffDays = Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays < 0) return `Overdue ${Math.abs(diffDays)}d`
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Tomorrow'
  return `In ${diffDays}d`
}

/** Person name only */
function ContactNameCell(props: ICellRendererParams<LeadRow>) {
  const { data } = props
  if (!data) return null
  return (
    <div className="flex items-center h-full">
      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--heading-text)' }}>
        {data.contact_name}
      </span>
    </div>
  )
}

/** Stage dot + label */
function ContactStageBadge(props: ICellRendererParams<LeadRow>) {
  const { data } = props
  if (!data) return null
  const stage = data.contact_stage
  const color = STAGE_COLORS[stage?.toLowerCase()] ?? '#9CA3AF'
  return (
    <div className="flex items-center h-full" style={{ gap: '5px' }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: '12px', fontWeight: 500, color, textTransform: 'capitalize' }}>{stage}</span>
    </div>
  )
}

/** Fit tier dot + label */
function FitTierBadge(props: ICellRendererParams<LeadRow>) {
  const { data } = props
  if (!data?.fit_tier) return null
  const tierKey = data.fit_tier.toLowerCase() as FitTierKey
  const palette = badges.fitTier[tierKey] ?? { bg: 'rgba(107,114,128,0.06)', text: '#6b7280' }
  return (
    <div className="flex items-center h-full" style={{ gap: '4px' }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: palette.text, opacity: 0.7 }} />
      <span style={{ fontSize: '11px', fontWeight: 500, color: palette.text }}>{data.fit_tier}</span>
    </div>
  )
}

/** Channel icons for messages */
function ChannelCell(props: ICellRendererParams<LeadRow>) {
  const { data } = props
  if (!data || data.messages.length === 0) return null
  const channels = [...new Set(data.messages.map((m) => m.channel))]
  return (
    <div className="flex items-center h-full" style={{ gap: '6px' }}>
      {channels.map((ch) => (
        ch === 'email'
          ? <Mail key={ch} style={{ width: 14, height: 14, color: 'var(--secondary-text)' }} />
          : <Linkedin key={ch} style={{ width: 14, height: 14, color: 'var(--secondary-text)' }} />
      ))}
      <span style={{ fontSize: '12px', color: 'var(--secondary-text)' }}>{data.messages.length}</span>
    </div>
  )
}

/** Next follow-up due */
function FollowUpCell(props: ICellRendererParams<LeadRow>) {
  const { data } = props
  if (!data) return null
  const label = getNextFollowUp(data)
  if (!label) return null
  const isOverdue = label.startsWith('Overdue')
  return (
    <div className="flex items-center h-full">
      <span
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: isOverdue ? '#dc2626' : label === 'Today' ? '#0284c7' : '#6b7280',
        }}
      >
        {label}
      </span>
    </div>
  )
}

/** Promote button */
function PromoteButton(props: ICellRendererParams<LeadRow> & { context: { onPromote?: (id: string) => void } }) {
  const { data, context } = props
  if (!data) return null
  return (
    <div className="flex items-center h-full">
      <button
        type="button"
        aria-label={`Promote ${data.company_name} to account`}
        onClick={(e) => { e.stopPropagation(); context.onPromote?.(data.lead_id) }}
        style={{
          fontSize: '12px', fontWeight: 500, color: 'var(--brand-coral)',
          background: 'transparent', border: 'none', cursor: 'pointer',
          borderRadius: '8px', padding: '4px 10px', transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => { (e.target as HTMLButtonElement).style.background = 'var(--brand-tint)' }}
        onMouseLeave={(e) => { (e.target as HTMLButtonElement).style.background = 'transparent' }}
      >
        Promote
      </button>
    </div>
  )
}

/** Company cell — clickable name linking to domain, only shown for first contact of each company */
function CompanyGroupCell(props: ICellRendererParams<LeadRow>) {
  const { data, api, node } = props
  if (!data) return null
  const rowIndex = node.rowIndex ?? 0
  if (rowIndex > 0) {
    const prevNode = api.getDisplayedRowAtIndex(rowIndex - 1)
    if (prevNode?.data && (prevNode.data as LeadRow).company_name === data.company_name) {
      return null
    }
  }
  if (data.domain) {
    return (
      <div className="flex items-center h-full">
        <a
          href={`https://${data.domain}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{ fontSize: '13px', fontWeight: 600, color: 'var(--heading-text)', textDecoration: 'none' }}
          onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
          onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
        >
          {data.company_name}
        </a>
      </div>
    )
  }
  return (
    <div className="flex items-center h-full">
      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--heading-text)' }}>{data.company_name}</span>
    </div>
  )
}

const columnDefs: ColDef<LeadRow>[] = [
  {
    headerName: 'Company',
    field: 'company_name',
    cellRenderer: CompanyGroupCell,
    minWidth: 160,
    width: 180,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Name',
    field: 'contact_name',
    cellRenderer: ContactNameCell,
    minWidth: 160,
    flex: 1,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Title',
    field: 'title',
    width: 160,
    resizable: true,
    sortable: true,
    cellStyle: { fontSize: '12px', color: '#6B7280' },
    valueFormatter: (params) => params.value ?? '',
  },
  {
    headerName: 'Stage',
    field: 'contact_stage',
    cellRenderer: ContactStageBadge,
    width: 110,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Fit',
    field: 'fit_tier',
    cellRenderer: FitTierBadge,
    width: 100,
    resizable: true,
    sortable: true,
  },
  {
    headerName: 'Channel',
    field: undefined,
    cellRenderer: ChannelCell,
    width: 90,
    resizable: false,
    sortable: false,
  },
  {
    headerName: 'Follow-up',
    field: undefined,
    cellRenderer: FollowUpCell,
    width: 100,
    resizable: true,
    sortable: false,
  },
  {
    headerName: 'Role',
    field: 'role',
    width: 110,
    resizable: true,
    sortable: true,
    cellStyle: { fontSize: '12px', color: '#6B7280', textTransform: 'capitalize' },
  },
  {
    headerName: 'Added',
    field: 'created_at',
    width: 90,
    resizable: true,
    sortable: true,
    valueFormatter: (params) => formatRelativeTime(params.value as string | null),
    cellStyle: { fontSize: '12px', color: '#6B7280' },
  },
  {
    headerName: '',
    field: undefined,
    cellRenderer: PromoteButton,
    width: 90,
    sortable: false,
    resizable: false,
    pinned: 'right' as const,
    suppressMovable: true,
  },
]

export function useLeadsColumns() {
  const gridApiRef = useRef<GridApi | null>(null)

  const getInitialState = (): GridState | undefined => {
    try {
      const raw = localStorage.getItem(COLUMN_STATE_KEY)
      if (!raw) return undefined
      const parsed = JSON.parse(raw) as ColumnState[]
      // Map persisted column state into ag-grid GridState sub-objects
      return {
        columnOrder: { orderedColIds: parsed.map((c) => c.colId) },
        columnSizing: {
          columnSizingModel: parsed
            .filter((c) => c.width != null)
            .map((c) => ({ colId: c.colId, width: c.width! })),
        },
        columnVisibility: {
          hiddenColIds: parsed.filter((c) => c.hide).map((c) => c.colId),
        },
      }
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
