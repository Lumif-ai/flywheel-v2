import { TrendingUp } from 'lucide-react'
import { useStreamGrowth } from '../hooks/useStreamDetail'

function getDensityBarColor(score: number): string {
  if (score >= 70) return 'bg-green-500'
  if (score >= 30) return 'bg-yellow-500'
  return 'bg-blue-500'
}

function getDensityBarTextColor(score: number): string {
  if (score >= 70) return 'text-green-600'
  if (score >= 30) return 'text-yellow-600'
  return 'text-blue-600'
}

function formatWeekLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

interface GrowthChartProps {
  streamId: string
}

export function GrowthChart({ streamId }: GrowthChartProps) {
  const { data, isLoading } = useStreamGrowth(streamId)

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="rounded-lg border p-4">
        <div className="flex items-end gap-2 h-40">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
              <div
                className="w-full rounded-t bg-muted animate-pulse"
                style={{ height: `${20 + Math.random() * 60}%` }}
              />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!data) return null

  // Too early state
  if (data.status === 'too_early') {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <TrendingUp className="size-8 text-muted-foreground/50 mb-3" />
        <p className="text-sm text-muted-foreground">
          {data.message || 'Growth tracking starts after your first week'}
        </p>
      </div>
    )
  }

  const weeks = data.weeks
  if (weeks.length === 0) return null

  const maxScore = Math.max(...weeks.map((w) => w.density_score), 1)
  const latestWeek = weeks[weeks.length - 1]

  return (
    <div className="rounded-lg border p-4 space-y-4">
      <div className="flex items-center gap-2">
        <TrendingUp className="size-4 text-muted-foreground" />
        <h3 className="text-sm font-medium">Knowledge Growth</h3>
      </div>

      {/* Bar chart */}
      <div className="flex items-end gap-2 h-40">
        {weeks.map((week) => {
          const heightPct = maxScore > 0 ? (week.density_score / maxScore) * 100 : 0
          const total = week.sources.meetings + week.sources.research + week.sources.integrations

          return (
            <div
              key={week.week_start}
              className="flex-1 flex flex-col items-center justify-end h-full gap-1"
            >
              {/* Percentage label */}
              <span className={`text-[10px] font-medium tabular-nums ${getDensityBarTextColor(week.density_score)}`}>
                {Math.round(week.density_score)}%
              </span>

              {/* Stacked bar */}
              <div
                className="w-full rounded-t overflow-hidden flex flex-col-reverse"
                style={{ height: `${Math.max(heightPct, 4)}%` }}
              >
                {total > 0 ? (
                  <>
                    {week.sources.meetings > 0 && (
                      <div
                        className="w-full bg-green-500"
                        style={{ height: `${(week.sources.meetings / total) * 100}%` }}
                      />
                    )}
                    {week.sources.research > 0 && (
                      <div
                        className="w-full bg-blue-500"
                        style={{ height: `${(week.sources.research / total) * 100}%` }}
                      />
                    )}
                    {week.sources.integrations > 0 && (
                      <div
                        className="w-full bg-purple-500"
                        style={{ height: `${(week.sources.integrations / total) * 100}%` }}
                      />
                    )}
                  </>
                ) : (
                  <div className={`w-full h-full ${getDensityBarColor(week.density_score)}`} />
                )}
              </div>

              {/* Week label */}
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {formatWeekLabel(week.week_start)}
              </span>
            </div>
          )
        })}
      </div>

      {/* Source legend */}
      <div className="flex gap-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
          Meetings
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
          Research
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-purple-500" />
          Integrations
        </span>
      </div>

      {/* This week's highlights */}
      {latestWeek.highlights.length > 0 && (
        <div className="border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">This week</p>
          <ul className="space-y-0.5">
            {latestWeek.highlights.map((h, i) => (
              <li key={i} className="text-sm text-muted-foreground">
                {h}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
