import { useState, useCallback } from 'react'
import { HistoryFilters } from '@/features/history/components/HistoryFilters'
import { HistoryList } from '@/features/history/components/HistoryList'
import { OutputViewer } from '@/features/history/components/OutputViewer'
import { useHistory, type HistoryFilters as Filters } from '@/features/history/hooks/useHistory'

const PAGE_SIZE = 20

export function HistoryPage() {
  const [filters, setFilters] = useState<Filters>({
    offset: 0,
    limit: PAGE_SIZE,
  })
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const { data, isLoading, isError, error, refetch } = useHistory(filters)

  const handleFiltersChange = useCallback((updates: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, ...updates }))
  }, [])

  const handleOffsetChange = useCallback((offset: number) => {
    setFilters((prev) => ({ ...prev, offset }))
  }, [])

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">History</h1>
        <p className="text-muted-foreground mt-1">Past skill executions</p>
      </div>

      <HistoryFilters filters={filters} onFiltersChange={handleFiltersChange} />

      <HistoryList
        data={data}
        isLoading={isLoading}
        isError={isError}
        error={error}
        offset={filters.offset}
        limit={filters.limit}
        onOffsetChange={handleOffsetChange}
        onSelectRun={setSelectedRunId}
        selectedRunId={selectedRunId}
        refetch={refetch}
      />

      <OutputViewer
        runId={selectedRunId}
        open={selectedRunId !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedRunId(null)
        }}
      />
    </div>
  )
}
