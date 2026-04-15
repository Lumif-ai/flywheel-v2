interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
}

export function MetricCard({ label, value, sub, accent }: MetricCardProps) {
  return (
    <div
      className="bg-white rounded-xl shadow-sm border p-4 flex flex-col gap-1"
      style={accent ? { borderLeft: '3px solid #E94D35' } : undefined}
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-2xl font-semibold text-foreground">{value}</span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  )
}
