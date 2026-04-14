import { useNavigate } from 'react-router'
import { FileSearch, CheckCircle, Download } from 'lucide-react'
import { useGateCounts } from '../hooks/useGateCounts'

const gates = [
  { key: 'review' as const, label: 'Review', icon: FileSearch },
  { key: 'approve' as const, label: 'Approve', icon: CheckCircle },
  { key: 'export' as const, label: 'Export', icon: Download },
] as const

export function GateStrip() {
  const { data, isLoading, isError } = useGateCounts()
  const navigate = useNavigate()

  if (isError) return null

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-background">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse bg-muted rounded-lg h-8 w-24" />
        ))}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-background">
      {gates.map(({ key, label, icon: Icon }) => {
        const gate = data[key]
        const hasItems = gate.count > 0

        return (
          <button
            key={key}
            onClick={() => {
              if (gate.oldest_project_id) {
                navigate(`/broker/projects/${gate.oldest_project_id}`)
              } else {
                navigate('/broker/projects')
              }
            }}
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium
              transition-colors cursor-pointer
              ${hasItems
                ? 'bg-amber-50 text-amber-800 hover:bg-amber-100 dark:bg-amber-950 dark:text-amber-200 dark:hover:bg-amber-900'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }
            `}
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
            <span className="font-bold">{gate.count}</span>
          </button>
        )
      })}
    </div>
  )
}
