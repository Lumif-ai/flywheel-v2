import { Briefcase, AlertCircle, Loader, CheckCircle } from 'lucide-react'
import type { DashboardStats } from '../types/broker'

interface KPICardProps {
  label: string
  value: number
  icon: React.ReactNode
  highlight?: boolean
}

function KPICard({ label, value, icon, highlight }: KPICardProps) {
  return (
    <div
      className={`rounded-xl border bg-white p-4 shadow-sm ${
        highlight && value > 0 ? 'border-amber-200 bg-amber-50/50' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
    </div>
  )
}

export function KPICards({ stats }: { stats: DashboardStats }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KPICard
        label="Total Projects"
        value={stats.total_projects}
        icon={<Briefcase className="h-5 w-5" />}
      />
      <KPICard
        label="Needs Action"
        value={stats.projects_needing_action}
        icon={<AlertCircle className="h-5 w-5" />}
        highlight
      />
      <KPICard
        label="Analyzing"
        value={stats.projects_by_status.analyzing ?? 0}
        icon={<Loader className="h-5 w-5" />}
      />
      <KPICard
        label="Complete"
        value={stats.projects_by_status.quotes_complete ?? 0}
        icon={<CheckCircle className="h-5 w-5" />}
      />
    </div>
  )
}
