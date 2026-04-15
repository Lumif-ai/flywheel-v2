import { AlertTriangle } from 'lucide-react'
import type { ComparisonCoverage } from '../../types/broker'

interface CriticalExclusionAlertProps {
  coverages: ComparisonCoverage[]
}

interface CriticalItem {
  coverage: string
  carrier: string
  detail: string | null
}

export function CriticalExclusionAlert({ coverages }: CriticalExclusionAlertProps) {
  const criticals: CriticalItem[] = coverages.flatMap((cov) =>
    cov.quotes
      .filter((q) => q.has_critical_exclusion)
      .map((q) => ({
        coverage: cov.coverage_type,
        carrier: q.carrier_name,
        detail: q.critical_exclusion_detail,
      }))
  )

  if (criticals.length === 0) return null

  return (
    <div
      className="rounded-lg p-4"
      style={{
        border: '1px solid rgba(239,68,68,0.4)',
        background: 'rgba(239,68,68,0.06)',
      }}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
        <div className="flex-1">
          <h4 className="text-red-700 font-medium text-sm">
            Critical Exclusions Detected
          </h4>
          <ul className="mt-2 space-y-1">
            {criticals.map((item, idx) => (
              <li key={idx} className="text-sm text-red-700">
                <span className="font-medium">{item.carrier}</span>
                {' — '}
                <span>{item.coverage}</span>
                {item.detail && (
                  <span className="text-red-600">: {item.detail}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
