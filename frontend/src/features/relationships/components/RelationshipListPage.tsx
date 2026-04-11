import { useState, useMemo, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import {
  Users, TrendingUp, Briefcase, DollarSign,
  Search, X, ChevronDown,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useRelationships } from '../hooks/useRelationships'
import { RelationshipTable } from './RelationshipTable'
import { EmptyState } from '@/components/ui/empty-state'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import type { RelationshipType, RelationshipListItem } from '../types/relationships'

const STALE_DAYS = 14

type ViewTab = 'all' | 'needs_action' | 'stale'

const TYPE_CONFIG: Record<
  RelationshipType,
  { label: string; icon: LucideIcon; emptyDescription: string }
> = {
  prospect: {
    label: 'Prospects',
    icon: Users,
    emptyDescription: 'Prospects from your Pipeline will appear here.',
  },
  customer: {
    label: 'Customers',
    icon: TrendingUp,
    emptyDescription: 'Closed deals will appear here once accounts are marked as customers.',
  },
  advisor: {
    label: 'Advisors',
    icon: Briefcase,
    emptyDescription: 'Add advisor relationships from the Pipeline to track them here.',
  },
  investor: {
    label: 'Investors',
    icon: DollarSign,
    emptyDescription: 'Investor relationships from the Pipeline will appear here.',
  },
}

const STATUS_OPTIONS = ['active', 'at_risk', 'churned', 'new'] as const

function isStale(item: RelationshipListItem): boolean {
  if (!item.last_activity_at) return true
  return (Date.now() - new Date(item.last_activity_at).getTime()) / 86400000 > STALE_DAYS
}

/* ─── Dropdown helper ──────────────────────────────────────────── */

function FilterDropdown({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string
  options: readonly string[]
  selected: string[]
  onToggle: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const hasActive = selected.length > 0

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors hover:bg-[#F3F4F6]"
        style={{
          background: hasActive ? 'rgba(233,77,53,0.06)' : 'transparent',
          color: hasActive ? '#E94D35' : '#6B7280',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        {label}
        {hasActive && (
          <span
            className="inline-flex items-center justify-center rounded-full"
            style={{
              background: 'rgba(233,77,53,0.12)',
              color: '#E94D35',
              fontSize: '10px',
              fontWeight: 700,
              width: '16px',
              height: '16px',
            }}
          >
            {selected.length}
          </span>
        )}
        <ChevronDown className="size-3" />
      </button>
      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-20 rounded-lg border bg-white py-1"
          style={{
            boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
            borderColor: '#E5E7EB',
            minWidth: '140px',
          }}
        >
          {options.map((opt) => {
            const active = selected.includes(opt)
            return (
              <button
                key={opt}
                onClick={() => onToggle(opt)}
                className="flex items-center gap-2 w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-[#FAFAFA]"
                style={{
                  color: active ? '#E94D35' : '#121212',
                  fontWeight: active ? 500 : 400,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <span
                  className="shrink-0 rounded-sm"
                  style={{
                    width: '14px',
                    height: '14px',
                    border: active ? '2px solid #E94D35' : '1.5px solid #D1D5DB',
                    background: active ? 'rgba(233,77,53,0.1)' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {active && (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1 4L3 6L7 2" stroke="#E94D35" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </span>
                <span className="capitalize">{opt.replace(/_/g, ' ')}</span>
              </button>
            )
          })}
          {selected.length > 0 && (
            <>
              <div style={{ height: '1px', background: '#F3F4F6', margin: '4px 0' }} />
              <button
                onClick={() => {
                  selected.forEach(onToggle)
                  setOpen(false)
                }}
                className="w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-[#FAFAFA]"
                style={{ color: '#E94D35', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Clear all
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

/* ─── Main component ───────────────────────────────────────────── */

export function RelationshipListPage({ type }: { type: RelationshipType }) {
  const navigate = useNavigate()
  const { data: items = [], isLoading, error, refetch } = useRelationships(type)
  const config = TYPE_CONFIG[type]

  const [search, setSearch] = useState('')
  const [activeView, setActiveView] = useState<ViewTab>('all')
  const [statusFilters, setStatusFilters] = useState<string[]>([])

  const needsActionCount = useMemo(() => items.filter((i) => i.signal_count > 0).length, [items])
  const staleCount = useMemo(() => items.filter(isStale).length, [items])

  const filtered = useMemo(() => {
    let result = items
    if (activeView === 'needs_action') result = result.filter((i) => i.signal_count > 0)
    else if (activeView === 'stale') result = result.filter(isStale)
    if (statusFilters.length > 0) result = result.filter((i) => statusFilters.includes(i.stage))
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          (i.domain && i.domain.toLowerCase().includes(q)) ||
          (i.primary_contact_name && i.primary_contact_name.toLowerCase().includes(q))
      )
    }
    return result
  }, [items, activeView, statusFilters, search])

  const toggleStatusFilter = (status: string) => {
    setStatusFilters((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    )
  }

  const VIEW_TABS: Array<{ key: ViewTab; label: string; count?: number }> = [
    { key: 'all', label: 'All', count: items.length },
    { key: 'needs_action', label: 'Needs Action', count: needsActionCount },
    { key: 'stale', label: 'Stale', count: staleCount },
  ]

  return (
    <div className="min-h-dvh" style={{ background: '#FFFFFF' }}>
      <div
        className="mx-auto w-full"
        style={{ maxWidth: '1440px', padding: '20px 24px' }}
      >
        {/* ── Header: title + view tabs on one line ──────────── */}
        <div className="flex items-baseline gap-6 mb-1">
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: '#121212',
              letterSpacing: '-0.01em',
              lineHeight: 1.3,
            }}
          >
            {config.label}
          </h1>
          <div className="flex items-center gap-0.5">
            {VIEW_TABS.map((tab) => {
              const isActive = activeView === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveView(tab.key)}
                  className="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
                  style={{
                    color: isActive ? '#E94D35' : '#6B7280',
                    background: isActive ? 'rgba(233,77,53,0.06)' : 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span
                      className="ml-1"
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: isActive ? '#E94D35' : '#9CA3AF',
                      }}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* ── Toolbar: search + filters + count ──────────────── */}
        <div
          className="flex items-center gap-2 py-2 mb-2"
          style={{ borderBottom: '1px solid #F3F4F6' }}
        >
          {/* Search */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0 max-w-[320px]">
            <Search className="size-3.5 shrink-0" style={{ color: '#9CA3AF' }} />
            <input
              type="text"
              placeholder={`Search ${config.label.toLowerCase()}...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 bg-transparent text-xs outline-none placeholder:text-[#D1D5DB]"
              style={{ color: '#121212', fontSize: '13px', minWidth: 0 }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="p-0.5 rounded hover:bg-[#F3F4F6] transition-colors"
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                <X className="size-3" style={{ color: '#9CA3AF' }} />
              </button>
            )}
          </div>

          {/* Divider */}
          <div style={{ width: '1px', height: '16px', background: '#E5E7EB' }} />

          {/* Status filter dropdown */}
          <FilterDropdown
            label="Status"
            options={STATUS_OPTIONS}
            selected={statusFilters}
            onToggle={toggleStatusFilter}
          />

          {/* Active filter chips (inline) */}
          {statusFilters.map((s) => (
            <button
              key={s}
              onClick={() => toggleStatusFilter(s)}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition-colors"
              style={{
                background: 'rgba(233,77,53,0.08)',
                color: '#E94D35',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <span className="capitalize">{s.replace(/_/g, ' ')}</span>
              <X className="size-2.5" />
            </button>
          ))}

          {/* Spacer + count */}
          <span className="ml-auto text-xs" style={{ color: '#9CA3AF', whiteSpace: 'nowrap' }}>
            {isLoading ? '' : `${filtered.length} of ${items.length}`}
          </span>
        </div>

        {/* ── Error ──────────────────────────────────────────── */}
        {error && !isLoading && (
          <div
            className="rounded-lg p-4 text-center mt-4"
            style={{ background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.15)' }}
          >
            <p style={{ color: '#dc2626', fontSize: '13px', marginBottom: '8px' }}>
              Failed to load {config.label.toLowerCase()}.
            </p>
            <button
              onClick={() => refetch()}
              style={{
                fontSize: '12px',
                fontWeight: 500,
                color: '#E94D35',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* ── Loading skeleton (table-shaped) ────────────────── */}
        {isLoading && (
          <div className="bg-white">
            {/* Header shimmer */}
            <div
              className="flex items-center gap-3 px-3"
              style={{ height: '36px', background: '#FAFAFA', borderBottom: '1px solid #E5E7EB' }}
            >
              {[120, 100, 70, 70, 50].map((w, i) => (
                <ShimmerSkeleton key={i} style={{ width: `${w}px`, height: '10px', borderRadius: '3px' }} />
              ))}
            </div>
            {/* Row shimmers */}
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3"
                style={{ height: '42px', borderBottom: '1px solid #F3F4F6' }}
              >
                <ShimmerSkeleton className="size-7 rounded-full shrink-0" />
                <ShimmerSkeleton style={{ width: '140px', height: '12px', borderRadius: '3px' }} />
                <ShimmerSkeleton style={{ width: '100px', height: '12px', borderRadius: '3px' }} />
                <ShimmerSkeleton style={{ width: '56px', height: '18px', borderRadius: '9px' }} />
                <ShimmerSkeleton style={{ width: '40px', height: '12px', borderRadius: '3px' }} />
                <ShimmerSkeleton style={{ width: '20px', height: '20px', borderRadius: '10px' }} />
              </div>
            ))}
          </div>
        )}

        {/* ── Empty: no data at all ──────────────────────────── */}
        {!isLoading && !error && items.length === 0 && (
          <EmptyState
            icon={config.icon}
            title={`No ${config.label.toLowerCase()} yet`}
            description={config.emptyDescription}
            actionLabel="Go to Pipeline"
            onAction={() => navigate('/pipeline')}
          />
        )}

        {/* ── Empty: filter/search no results ────────────────── */}
        {!isLoading && items.length > 0 && filtered.length === 0 && (
          <div className="text-center py-12">
            <Search className="size-8 mx-auto mb-2" style={{ color: '#D1D5DB' }} />
            <p style={{ fontSize: '14px', color: '#121212', fontWeight: 500, marginBottom: '4px' }}>
              No matching {config.label.toLowerCase()}
            </p>
            <p style={{ fontSize: '12px', color: '#9CA3AF' }}>
              Try adjusting your search or filters.
            </p>
          </div>
        )}

        {/* ── Table ──────────────────────────────────────────── */}
        {!isLoading && filtered.length > 0 && (
          <RelationshipTable items={filtered} type={type} />
        )}
      </div>
    </div>
  )
}
