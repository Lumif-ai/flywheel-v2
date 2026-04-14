import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { Search, Briefcase } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useBrokerProjects } from '../hooks/useBrokerProjects'
import { ProjectPipelineGrid } from '../components/ProjectPipelineGrid'
import { CreateProjectDialog } from '../components/CreateProjectDialog'

const PAGE_SIZE = 25

const STATUS_OPTIONS = [
  { value: undefined, label: 'All' },
  { value: 'new_request', label: 'New' },
  { value: 'analyzing', label: 'Analyzing' },
  { value: 'gaps_identified', label: 'Gaps Found' },
  { value: 'soliciting', label: 'Soliciting' },
  { value: 'quotes_complete', label: 'Quotes Done' },
  { value: 'recommended', label: 'Recommended' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'bound', label: 'Bound' },
] as const

export function BrokerProjectsPage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // 300ms debounce for search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput)
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Reset offset when status changes
  useEffect(() => {
    setOffset(0)
  }, [status])

  const { data, isLoading } = useBrokerProjects({
    limit: PAGE_SIZE,
    offset,
    status,
    search: debouncedSearch || undefined,
  })

  const hasFilters = status !== undefined || debouncedSearch !== ''
  const isEmpty = !isLoading && (data?.items ?? []).length === 0

  function clearFilters() {
    setStatus(undefined)
    setSearchInput('')
    setDebouncedSearch('')
    setOffset(0)
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-foreground">Projects</h1>
        <CreateProjectDialog />
      </div>

      {/* Search + Status Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search input */}
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="rounded-lg border bg-white px-3 py-2 pl-9 text-sm w-full focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* Status chips */}
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.label}
            type="button"
            onClick={() => setStatus(opt.value)}
            className={`rounded-full px-3 py-1 text-sm font-medium cursor-pointer transition-colors ${
              status === opt.value
                ? 'bg-foreground text-background'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Empty states */}
      {isEmpty && !hasFilters && (
        <div className="flex flex-col items-center justify-center rounded-xl border bg-white py-16 shadow-sm">
          <Briefcase className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold text-foreground">No projects yet</h2>
          <p className="text-muted-foreground mt-1 mb-4">
            Add your carriers first, then create your first project.
          </p>
          <Button onClick={() => navigate('/broker/carriers')}>Add Carriers</Button>
        </div>
      )}

      {isEmpty && hasFilters && (
        <div className="flex flex-col items-center justify-center rounded-xl border bg-white py-16 shadow-sm">
          <Search className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold text-foreground">
            No projects match your filters
          </h2>
          <p className="text-muted-foreground mt-1 mb-4">
            Try a different search term or status filter.
          </p>
          <Button variant="outline" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>
      )}

      {/* Grid */}
      {!isEmpty && (
        <ProjectPipelineGrid
          projects={data?.items ?? []}
          total={data?.total ?? 0}
          isLoading={isLoading}
          offset={offset}
          limit={PAGE_SIZE}
          onPageChange={setOffset}
          onRowClick={(id) => navigate(`/broker/projects/${id}`)}
          storageKey="broker-projects-page"
        />
      )}
    </div>
  )
}
