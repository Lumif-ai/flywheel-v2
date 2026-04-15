import { useState, useMemo, useCallback } from 'react'
import { BarChart3, Info, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import type { ComparisonMatrix } from '../../types/broker'
import { exportComparison } from '../../api'
import { getUniqueCarriers } from './comparison-utils'
import { CriticalExclusionAlert } from './CriticalExclusionAlert'
import { ComparisonToolbar } from './ComparisonToolbar'
import { ComparisonTabs } from './ComparisonTabs'

interface ComparisonViewProps {
  data: ComparisonMatrix
  currency: string
  projectId: string
}

function deriveInsightText(data: ComparisonMatrix): string {
  const counts: Record<string, number> = {}
  for (const cov of data.coverages) {
    for (const q of cov.quotes) {
      if (q.is_recommended) {
        counts[q.carrier_name] = (counts[q.carrier_name] ?? 0) + 1
      }
    }
  }
  const entries = Object.entries(counts)
  if (!entries.length) return 'Insufficient quote data to generate a recommendation.'
  const top = entries.reduce((a, b) => (a[1] >= b[1] ? a : b))[0]
  const covCount = counts[top]
  return `${top} is recommended for ${covCount} of ${data.total_coverages} coverage${data.total_coverages === 1 ? '' : 's'} — lowest premium without critical exclusions.`
}

export function ComparisonView({ data, currency, projectId }: ComparisonViewProps) {
  const allCarriers = useMemo(
    () => getUniqueCarriers(data.coverages),
    [data.coverages]
  )

  const [selectedCarriers, setSelectedCarriers] = useState<Set<string>>(
    () => new Set(allCarriers.map((c) => c.name))
  )
  const [showDifferencesOnly, setShowDifferencesOnly] = useState(true)
  const [highlightBest, setHighlightBest] = useState(false)
  const [viewMode, setViewMode] = useState<'interactive' | 'pdf'>('interactive')

  const onToggleCarrier = useCallback(
    (name: string) => {
      setSelectedCarriers((prev) => {
        const next = new Set(prev)
        if (next.has(name)) {
          // At least 1 carrier must remain selected
          if (next.size <= 1) return prev
          next.delete(name)
        } else {
          next.add(name)
        }
        return next
      })
    },
    []
  )

  const [isExporting, setIsExporting] = useState(false)

  const handleExport = useCallback(async () => {
    setIsExporting(true)
    try {
      const quoteIds = data.coverages
        .flatMap((c) => c.quotes)
        .filter((q) => selectedCarriers.has(q.carrier_name))
        .map((q) => q.quote_id)
      await exportComparison(projectId, quoteIds.length > 0 ? quoteIds : undefined)
      toast.success('Comparison exported successfully')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExporting(false)
    }
  }, [data.coverages, selectedCarriers, projectId])

  const filteredCoverages = useMemo(
    () =>
      data.coverages.map((cov) => ({
        ...cov,
        quotes: cov.quotes.filter((q) => selectedCarriers.has(q.carrier_name)),
      })),
    [data.coverages, selectedCarriers]
  )

  const insightText = useMemo(() => deriveInsightText(data), [data])

  if (data.coverages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <BarChart3 className="h-10 w-10 text-muted-foreground mb-3" />
        <h3 className="text-lg font-medium">No quotes to compare yet</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Add carriers and upload quotes to see the comparison matrix.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 1. Toolbar with Interactive/PDF toggle */}
      <ComparisonToolbar
        showDifferencesOnly={showDifferencesOnly}
        onToggleDifferences={() => setShowDifferencesOnly((v) => !v)}
        highlightBest={highlightBest}
        onToggleHighlight={() => setHighlightBest((v) => !v)}
        onExport={handleExport}
        isExporting={isExporting}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      {/* 2. Partial comparison banner */}
      {data.partial && (
        <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg">
          <Info className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-700">
            Some carriers have not yet submitted quotes. This comparison is incomplete.
          </p>
        </div>
      )}

      {/* 3. Critical exclusion alert */}
      <CriticalExclusionAlert coverages={data.coverages} />

      {/* 4. AI Insight card */}
      {insightText !== 'Insufficient quote data to generate a recommendation.' && (
        <div
          className="rounded-lg p-4"
          style={{
            background: 'rgba(233,77,53,0.06)',
            border: '1px solid rgba(233,77,53,0.3)',
            borderRadius: '8px',
          }}
        >
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 shrink-0 mt-0.5" style={{ color: '#E94D35' }} />
            <div className="flex-1">
              <h4 className="font-medium text-sm" style={{ color: '#E94D35' }}>
                AI Insight
              </h4>
              <p className="mt-1 text-sm text-gray-700">{insightText}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Generated from quote comparison data. A full AI narrative will be available in a future update.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 5. Comparison grid */}
      <ComparisonTabs
        coverages={filteredCoverages}
        currency={currency}
        selectedCarriers={selectedCarriers}
        onToggleCarrier={onToggleCarrier}
        showDifferencesOnly={showDifferencesOnly}
        highlightBest={highlightBest}
        viewMode={viewMode}
      />
    </div>
  )
}
