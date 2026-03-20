export function HQPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Welcome to Flywheel</h1>
        <p className="text-muted-foreground mt-1">Knowledge compounding engine</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border p-6 space-y-2">
          <h2 className="font-semibold text-foreground">Recent Skills</h2>
          <p className="text-sm text-muted-foreground">Coming soon</p>
        </div>

        <div className="rounded-xl border p-6 space-y-2">
          <h2 className="font-semibold text-foreground">Quick Actions</h2>
          <p className="text-sm text-muted-foreground">Coming soon</p>
        </div>

        <div className="rounded-xl border p-6 space-y-2">
          <h2 className="font-semibold text-foreground">Context Store Summary</h2>
          <p className="text-sm text-muted-foreground">Coming soon</p>
        </div>
      </div>
    </div>
  )
}
