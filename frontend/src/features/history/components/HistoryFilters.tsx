import { useCallback, useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useSkillsList, type HistoryFilters as Filters } from '../hooks/useHistory'

const STATUS_OPTIONS = ['all', 'completed', 'failed', 'running', 'pending'] as const

const DATE_PRESETS = [
  { label: 'All time', value: '' },
  { label: 'Today', value: 'today' },
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
] as const

function getDateFrom(preset: string): string | undefined {
  if (!preset) return undefined
  const now = new Date()
  if (preset === 'today') {
    return now.toISOString().split('T')[0]
  }
  if (preset === '7d') {
    now.setDate(now.getDate() - 7)
    return now.toISOString().split('T')[0]
  }
  if (preset === '30d') {
    now.setDate(now.getDate() - 30)
    return now.toISOString().split('T')[0]
  }
  return undefined
}

interface HistoryFiltersProps {
  filters: Filters
  onFiltersChange: (updates: Partial<Filters>) => void
}

export function HistoryFilters({ filters, onFiltersChange }: HistoryFiltersProps) {
  const { data: skills } = useSkillsList()
  const [searchInput, setSearchInput] = useState(filters.search ?? '')
  const [datePreset, setDatePreset] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value)
      clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onFiltersChange({ search: value || undefined, offset: 0 })
      }, 300)
    },
    [onFiltersChange],
  )

  useEffect(() => {
    return () => clearTimeout(debounceRef.current)
  }, [])

  const activeStatus = filters.status ?? 'all'

  return (
    <div className="space-y-3">
      {/* Search + Skill filter row */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search runs..."
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-8"
          />
        </div>

        <select
          value={filters.skill_name ?? ''}
          onChange={(e) =>
            onFiltersChange({
              skill_name: e.target.value || undefined,
              offset: 0,
            })
          }
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <option value="">All skills</option>
          {skills?.map((s) => (
            <option key={s.name} value={s.name}>
              {s.display_name}
            </option>
          ))}
        </select>

        <select
          value={datePreset}
          onChange={(e) => {
            setDatePreset(e.target.value)
            onFiltersChange({
              date_from: getDateFrom(e.target.value),
              offset: 0,
            })
          }}
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {DATE_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      {/* Status filter row */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_OPTIONS.map((status) => (
          <Button
            key={status}
            variant="ghost"
            size="xs"
            onClick={() =>
              onFiltersChange({
                status: status === 'all' ? undefined : status,
                offset: 0,
              })
            }
            className="px-0"
          >
            <Badge
              variant={activeStatus === status ? 'default' : 'outline'}
              className="cursor-pointer capitalize"
            >
              {status}
            </Badge>
          </Button>
        ))}
      </div>
    </div>
  )
}
