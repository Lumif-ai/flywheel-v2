import { typography } from '@/lib/design-tokens'

const KNOWN_KEYS: Record<string, string> = {
  industry: 'Industry',
  employee_count: 'Employees',
  funding: 'Funding',
  location: 'Location',
  description: 'Description',
  website: 'Website',
}

interface IntelSidebarProps {
  intel: Record<string, unknown>
}

function formatValue(value: unknown): string {
  if (value == null) return '--'
  if (typeof value === 'string') return value
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return JSON.stringify(value)
}

export function IntelSidebar({ intel }: IntelSidebarProps) {
  const entries = Object.entries(intel)
  const knownEntries = entries.filter(([k]) => k in KNOWN_KEYS)
  const unknownEntries = entries.filter(([k]) => !(k in KNOWN_KEYS))

  return (
    <div>
      <h2
        className="text-foreground mb-4"
        style={{
          fontSize: typography.sectionTitle.size,
          fontWeight: typography.sectionTitle.weight,
          lineHeight: typography.sectionTitle.lineHeight,
        }}
      >
        Intel
      </h2>

      {entries.length === 0 ? (
        <p className="text-muted-foreground text-sm">No intel available</p>
      ) : (
        <div className="space-y-4">
          {knownEntries.map(([key, value]) => (
            <div key={key}>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {KNOWN_KEYS[key]}
              </p>
              {key === 'website' && typeof value === 'string' ? (
                <a
                  href={value.startsWith('http') ? value : `https://${value}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline break-all"
                >
                  {value}
                </a>
              ) : key === 'description' ? (
                <p className="text-sm text-foreground leading-relaxed">
                  {formatValue(value)}
                </p>
              ) : (
                <p className="text-sm text-foreground">{formatValue(value)}</p>
              )}
            </div>
          ))}

          {unknownEntries.length > 0 && knownEntries.length > 0 && (
            <hr className="border-border" />
          )}

          {unknownEntries.map(([key, value]) => (
            <div key={key}>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {key.replace(/_/g, ' ')}
              </p>
              <p className="text-sm text-foreground">{formatValue(value)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
