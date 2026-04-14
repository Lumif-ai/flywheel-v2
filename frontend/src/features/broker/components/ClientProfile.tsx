import { Building2, User, Mail, Phone, Briefcase, MapPin } from 'lucide-react'

interface ClientProfileProps {
  metadata: Record<string, unknown> | null
}

function getStr(metadata: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const val = metadata[key]
    if (typeof val === 'string' && val.trim()) return val
  }
  return undefined
}

const FIELDS = [
  { label: 'Company', keys: ['client_company', 'company_name'], icon: Building2 },
  { label: 'Contact', keys: ['client_name', 'contact_name'], icon: User },
  { label: 'Email', keys: ['client_email', 'contact_email'], icon: Mail },
  { label: 'Phone', keys: ['client_phone', 'phone'], icon: Phone },
  { label: 'Industry', keys: ['industry'], icon: Briefcase },
  { label: 'Location', keys: ['client_location', 'location'], icon: MapPin },
] as const

export function ClientProfile({ metadata }: ClientProfileProps) {
  const items = metadata
    ? FIELDS.map((f) => ({
        ...f,
        value: getStr(metadata, ...f.keys),
      })).filter((f) => f.value)
    : []

  return (
    <div className="rounded-xl border p-4">
      <h3 className="text-sm font-semibold mb-3">Client Profile</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No client information available. Client details will appear here after
          AI analysis.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {items.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.label} className="flex items-start gap-2">
                <Icon className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <p className="text-sm font-medium">{item.value}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
