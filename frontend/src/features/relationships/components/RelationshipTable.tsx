import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router'
import {
  ArrowUpDown, ArrowUp, ArrowDown, Building2,
  Circle, User, Clock, Zap,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import type { RelationshipListItem, RelationshipType } from '../types/relationships'

/* ─── Types ────────────────────────────────────────────────────── */

type SortField = 'name' | 'domain' | 'stage' | 'primary_contact_name' | 'last_activity_at' | 'signal_count'
type SortDir = 'asc' | 'desc'

/* ─── Avatar color hash ────────────────────────────────────────── */

const AVATAR_PALETTE = [
  { bg: 'rgba(34,197,94,0.12)', text: '#16a34a' },   // sage
  { bg: 'rgba(59,130,246,0.12)', text: '#2563eb' },   // blue
  { bg: 'rgba(245,158,11,0.12)', text: '#d97706' },   // amber
  { bg: 'rgba(168,85,247,0.12)', text: '#9333ea' },   // purple
  { bg: 'rgba(20,184,166,0.12)', text: '#0d9488' },   // teal
  { bg: 'rgba(233,77,53,0.12)', text: '#E94D35' },    // coral
]

function avatarColor(name: string) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length]
}

/* ─── Helpers ──────────────────────────────────────────────────── */

function getInitials(name: string): string {
  return name.split(' ').filter(Boolean).slice(0, 2).map((n) => n[0].toUpperCase()).join('')
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diffMs = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMs / 3600000)
  const days = Math.floor(diffMs / 86400000)
  if (mins < 1) return 'just now'
  if (hours < 1) return `${mins}m`
  if (hours < 24) return `${hours}h`
  if (days < 30) return `${days}d`
  return `${Math.floor(days / 30)}mo`
}

function statusStyle(status: string): React.CSSProperties {
  switch (status) {
    case 'active': return { background: 'rgba(34,197,94,0.08)', color: '#16a34a' }
    case 'at_risk': return { background: 'rgba(245,158,11,0.08)', color: '#d97706' }
    case 'churned': return { background: 'rgba(239,68,68,0.08)', color: '#dc2626' }
    default: return { background: 'rgba(107,114,128,0.06)', color: '#6b7280' }
  }
}

const STALE_DAYS = 14

/* ─── Column config ────────────────────────────────────────────── */

const COLUMNS: Array<{
  field: SortField
  label: string
  icon: React.ElementType
  minWidth: string
}> = [
  { field: 'name', label: 'Name', icon: Building2, minWidth: '200px' },
  { field: 'primary_contact_name', label: 'Contact', icon: User, minWidth: '140px' },
  { field: 'stage', label: 'Status', icon: Circle, minWidth: '90px' },
  { field: 'last_activity_at', label: 'Last Active', icon: Clock, minWidth: '90px' },
  { field: 'signal_count', label: 'Signals', icon: Zap, minWidth: '72px' },
]

/* ─── Table styles (shared constants) ──────────────────────────── */

const CELL_PX = '12px'
const CELL_PY = '8px'
const HEADER_H = '36px'
const ROW_H = '42px'
const FONT_CELL = '13px'
const FONT_HEADER = '11px'

/* ─── Component ────────────────────────────────────────────────── */

interface RelationshipTableProps {
  items: RelationshipListItem[]
  type: RelationshipType
}

export function RelationshipTable({ items, type }: RelationshipTableProps) {
  const navigate = useNavigate()
  const [sortField, setSortField] = useState<SortField>('signal_count')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1
      switch (sortField) {
        case 'name':
          return dir * a.name.localeCompare(b.name)
        case 'domain':
          return dir * (a.domain ?? '').localeCompare(b.domain ?? '')
        case 'stage':
          return dir * a.stage.localeCompare(b.stage)
        case 'primary_contact_name':
          return dir * (a.primary_contact_name ?? '').localeCompare(b.primary_contact_name ?? '')
        case 'last_activity_at': {
          const aT = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0
          const bT = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0
          return dir * (aT - bT)
        }
        case 'signal_count':
          return dir * (a.signal_count - b.signal_count)
        default: return 0
      }
    })
  }, [items, sortField, sortDir])

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir(field === 'name' ? 'asc' : 'desc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="size-3 opacity-0 group-hover/th:opacity-40 transition-opacity" />
    return sortDir === 'asc'
      ? <ArrowUp className="size-3" style={{ color: '#E94D35' }} />
      : <ArrowDown className="size-3" style={{ color: '#E94D35' }} />
  }

  const isStale = (item: RelationshipListItem) => {
    if (!item.last_activity_at) return true
    return (Date.now() - new Date(item.last_activity_at).getTime()) / 86400000 > STALE_DAYS
  }

  return (
    <div className="overflow-x-auto bg-white">
      <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ height: HEADER_H, background: '#FAFAFA' }}>
            {COLUMNS.map(({ field, label, icon: Icon, minWidth }) => (
              <th
                key={field}
                onClick={() => toggleSort(field)}
                className={`group/th cursor-pointer select-none ${field === 'name' ? 'sticky left-0 z-10' : ''}`}
                style={{
                  padding: `0 ${CELL_PX}`,
                  minWidth,
                  fontSize: FONT_HEADER,
                  fontWeight: 600,
                  color: '#9CA3AF',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  borderBottom: '1px solid #E5E7EB',
                  background: field === 'name' ? '#FAFAFA' : undefined,
                  whiteSpace: 'nowrap',
                }}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Icon className="size-3.5" style={{ color: '#D1D5DB' }} />
                  {label}
                  <SortIcon field={field} />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((item, index) => {
            const stale = isStale(item)
            const hasSignals = item.signal_count > 0
            const colors = avatarColor(item.name)

            return (
              <tr
                key={item.id}
                onClick={() => navigate(`/relationships/${item.id}?fromType=${type}`)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') navigate(`/relationships/${item.id}?fromType=${type}`)
                }}
                className="group/row cursor-pointer transition-colors duration-150 hover:bg-[#FAFAFA] focus-visible:outline-none focus-visible:bg-[rgba(233,77,53,0.04)]"
                style={{
                  height: ROW_H,
                  animationDelay: `${Math.min(index, 10) * 30}ms`,
                  // @ts-expect-error CSS custom property
                  '--row-index': index,
                }}
              >
                {/* Name — sticky with signal dot */}
                <td
                  className="sticky left-0 z-10 transition-colors duration-150 group-hover/row:bg-[#FAFAFA] group-focus-visible/row:bg-[rgba(233,77,53,0.04)]"
                  style={{
                    padding: `${CELL_PY} ${CELL_PX}`,
                    borderBottom: '1px solid #F3F4F6',
                    background: 'white',
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {/* Signal dot */}
                    <div
                      className="shrink-0"
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: hasSignals ? '#E94D35' : 'transparent',
                      }}
                    />
                    <Avatar className="size-7 shrink-0">
                      <AvatarFallback
                        style={{
                          background: colors.bg,
                          color: colors.text,
                          fontSize: '10px',
                          fontWeight: 600,
                        }}
                      >
                        {getInitials(item.name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <p
                        className="truncate"
                        style={{
                          fontSize: FONT_CELL,
                          fontWeight: 600,
                          color: '#121212',
                          lineHeight: 1.3,
                        }}
                      >
                        {item.name}
                      </p>
                      {item.domain && (
                        <p className="truncate" style={{ fontSize: '11px', color: '#9CA3AF', lineHeight: 1.3 }}>
                          {item.domain}
                        </p>
                      )}
                    </div>
                  </div>
                </td>

                {/* Contact */}
                <td style={{ padding: `${CELL_PY} ${CELL_PX}`, borderBottom: '1px solid #F3F4F6' }}>
                  {item.primary_contact_name ? (
                    <span style={{ fontSize: FONT_CELL, color: '#121212' }}>
                      {item.primary_contact_name}
                    </span>
                  ) : (
                    <span
                      className="opacity-0 group-hover/row:opacity-100 transition-opacity duration-150"
                      style={{ fontSize: '12px', color: '#D1D5DB' }}
                    >
                      Add contact
                    </span>
                  )}
                </td>

                {/* Status */}
                <td style={{ padding: `${CELL_PY} ${CELL_PX}`, borderBottom: '1px solid #F3F4F6' }}>
                  <span
                    className="inline-flex items-center rounded-full px-2 py-px text-xs font-medium"
                    style={{ ...statusStyle(item.stage), fontSize: '11px', lineHeight: '18px' }}
                  >
                    {item.stage.replace(/_/g, ' ')}
                  </span>
                </td>

                {/* Last Active */}
                <td style={{ padding: `${CELL_PY} ${CELL_PX}`, borderBottom: '1px solid #F3F4F6' }}>
                  {item.last_activity_at ? (
                    <span
                      style={{
                        fontSize: FONT_CELL,
                        color: stale ? '#d97706' : '#6B7280',
                        fontWeight: stale ? 500 : 400,
                      }}
                    >
                      {formatTimeAgo(item.last_activity_at)}
                      {stale && (
                        <span style={{ fontSize: '11px', color: '#d97706', marginLeft: '4px' }}>
                          overdue
                        </span>
                      )}
                    </span>
                  ) : (
                    <span
                      className="opacity-0 group-hover/row:opacity-100 transition-opacity duration-150"
                      style={{ fontSize: '12px', color: '#D1D5DB' }}
                    >
                      No activity
                    </span>
                  )}
                </td>

                {/* Signals */}
                <td style={{ padding: `${CELL_PY} ${CELL_PX}`, borderBottom: '1px solid #F3F4F6' }}>
                  {item.signal_count > 0 ? (
                    <span
                      className="inline-flex items-center justify-center rounded-full"
                      style={{
                        background: 'rgba(233,77,53,0.1)',
                        color: '#E94D35',
                        fontSize: '11px',
                        fontWeight: 600,
                        minWidth: '20px',
                        height: '20px',
                        padding: '0 5px',
                      }}
                    >
                      {item.signal_count}
                    </span>
                  ) : null}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
